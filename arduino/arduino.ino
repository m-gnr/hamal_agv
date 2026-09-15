#include <Arduino.h>
#include <cmath>
#include "soc/rtc_cntl_reg.h"

// -------------------- CONFIG ---------------------------
#include "src/config/config_pins.h"
#include "src/config/config_robot.h"

// -------------------- MODULES --------------------------
#include "src/encoder/encoder.h"
#include "src/kinematics/kinematics.h"
#include "src/imu/imu.h"
#include "src/control/velocity_cmd.h"
#include "src/control/wheel_pid.h"
#include "src/control/fork_controller.h"
#include "src/motor/motor.h"
#include "src/motor/fork_motor.h"
#include "src/safety/fork_limits.h"
#include "src/comm/serial_comm.h"
#include "src/comm/fork_protocol.h"
#include "src/timing/timing.h"
#include "src/obstacle/obstacle.h"

// ======================================================
// OBJECTS
// ======================================================

SerialComm serial;

Encoder leftEncoder(ENC_L_A, ENC_L_B, ENC_L_DIRECTION);
Encoder rightEncoder(ENC_R_A, ENC_R_B, ENC_R_DIRECTION);

Obstacle obstacle(OBSTACLE_PIN);                 //  E18-D80NK mesafe

IMU imu(IMU_CS, IMU_INT, IMU_RST);

Kinematics kinematics(
    ENCODER_CPR_LEFT,
    ENCODER_CPR_RIGHT,
    WHEEL_RADIUS_M,
    TRACK_WIDTH_M
);

VelocityCmd velocityCmd(WHEEL_RADIUS_M, TRACK_WIDTH_M);

WheelPID pidL;
WheelPID pidR;

Motor motorL(MOTOR_L_IN1, MOTOR_L_IN2, PWM_MAX);
Motor motorR(MOTOR_R_IN1, MOTOR_R_IN2, PWM_MAX);

Timing controlTimer(CONTROL_DT_S);
Timing encTxTimer(ENC_TX_DT_S);
Timing imuTxTimer(IMU_TX_DT_S);
Timing obsTxTimer(0.05f);                         // mesafe 20 Hz
Timing safetyTxTimer(0.1f);                       // : mod switch 10 Hz

// ======================================================
// IMU TASK (Core 0)
// ======================================================
TaskHandle_t imuTaskHandle = NULL;

void imuTask(void* pvParameters) {
    while (true) {
        if (imu.dataReady) {
            imu.dataReady = false;
            imu.update();
        }
        vTaskDelay(1);
    }
}

// ======================================================
// ISR
// ======================================================
void IRAM_ATTR onImuInt() {
    imu.dataReady = true;
}

// ======================================================
// SETUP
// ======================================================
void setup() {
    CLEAR_PERI_REG_MASK(RTC_CNTL_FIB_SEL_REG, RTC_CNTL_FIB_SEL);

    Serial.begin(SERIAL_BAUDRATE);
    serial.begin(SERIAL_BAUDRATE);
    delay(1500);

    Serial.println("Hamals Firmware - SERIAL MODE");

    leftEncoder.begin();
    rightEncoder.begin();

    if (!imu.begin()) {
        Serial.println("IMU init failed");
        while (1) {}
    }

    motorL.begin();
    motorR.begin();
    hamals::fork_motor::begin();
    hamals::fork_limits::begin();
    hamals::fork_controller::begin();

    pidL.setGains(WHEEL_PID_KP, WHEEL_PID_KI, WHEEL_PID_KD);
    pidR.setGains(WHEEL_PID_KP, WHEEL_PID_KI, WHEEL_PID_KD);

    pidL.setOutputLimits(-PWM_MAX, PWM_MAX);
    pidR.setOutputLimits(-PWM_MAX, PWM_MAX);

    pidL.setRampLimit(WHEEL_PID_RAMP_STEP);
    pidR.setRampLimit(WHEEL_PID_RAMP_STEP);

    pidL.setDeadzone(PWM_MIN_START_L, PWM_MIN_RUN_L, DEADZONE_CMD_EPS, DEADZONE_MEAS_EPS);
    pidR.setDeadzone(PWM_MIN_START_R, PWM_MIN_RUN_R, DEADZONE_CMD_EPS, DEADZONE_MEAS_EPS);

    pinMode(IMU_INT, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(IMU_INT), onImuInt, FALLING);

    xTaskCreatePinnedToCore(
        imuTask,
        "imuTask",
        4096,
        NULL,
        1,
        &imuTaskHandle,
        0
    );

    controlTimer.reset();
    encTxTimer.reset();
    imuTxTimer.reset();

    delayMicroseconds(10000);
    imuTxTimer.reset();

    obstacle.begin();
    obsTxTimer.reset();

    pinMode(MODE_PIN_MANUEL, INPUT_PULLUP);       // : mod switch (manuel)
    pinMode(MODE_PIN_OTONOM, INPUT_PULLUP);       // : mod switch (otonom)
    safetyTxTimer.reset();                        // : 

    Serial.println("Ready");
}

// ======================================================
// LOOP (Core 1)
// ======================================================
void loop() {
    serial.update();
    hamals::fork_limits::update();
    hamals::fork_controller::update();
    hamals::fork_protocol::publishForkStateIfDue();

    obstacle.update();

    static int32_t last_dL_ctrl = 0;
    static int32_t last_dR_ctrl = 0;

    static int32_t enc_accum_L = 0;
    static int32_t enc_accum_R = 0;

    const int32_t dL_step = leftEncoder.readDelta();
    const int32_t dR_step = rightEncoder.readDelta();

    last_dL_ctrl = dL_step;
    last_dR_ctrl = dR_step;

    enc_accum_L += dL_step;
    enc_accum_R += dR_step;

    bool sent_any = false;
    uint32_t t_us = 0;

    if (encTxTimer.tick()) {
        if (!sent_any) { t_us = micros(); sent_any = true; }
        serial.sendEnc(t_us, enc_accum_L, enc_accum_R);
        enc_accum_L = 0;
        enc_accum_R = 0;
    }

    if (imuTxTimer.tick()) {
        if (!sent_any) { t_us = micros(); sent_any = true; }
        serial.sendImu(t_us, imu.getGz(), imu.getAx(), imu.getAy(), imu.getAz());
    }

    // : mesafe sensoru durumu.
    //   (A) simdilik SADECE Serial'e (test). ROS'a gondermek icin
    //       serial_comm'a sendObstacle ekleyip alttaki satiri ac.
    if (obsTxTimer.tick()) {
        // serial.sendObstacle(obstacle.detected());   // <<< serial_comm hazir olunca ac
        Serial.print("OBSTACLE=");
        serial.sendObstacle(micros(), obstacle.detected());
    }

    // : Manuel/Otonom switch (2 pin) -> ROS ($SAFETY,t_us,estop,manual)
    if (safetyTxTimer.tick()) {
        const bool sel_manuel = (digitalRead(MODE_PIN_MANUEL) == LOW);  // : manuel secili
        const bool sel_otonom = (digitalRead(MODE_PIN_OTONOM) == LOW);  // : otonom secili
        bool manual;
        if (sel_manuel && !sel_otonom)      manual = true;   // : manuel secili
        else if (sel_otonom && !sel_manuel) manual = false;  // : otonom secili
        else                                manual = true;   // : belirsiz/kopuk -> manuel (guvenli)
        serial.sendSafety(micros(), false, manual);          // : estop=0 (henuz donanim yok)
    }

    if (!controlTimer.tick())
        return;

    const float dt = controlTimer.dt();

    static float v_target = 0.0f;
    static float w_target = 0.0f;
    static bool base_motion_active = false;

    if (serial.hasCmdVel()) {
        const CmdVel cmd = serial.getCmdVel();
        v_target = cmd.v;
        w_target = cmd.w;
        base_motion_active =
            fabs(v_target) >= 0.01f || fabs(w_target) >= 0.01f;
    }

    if (base_motion_active &&
        serial.isCmdWatchdogTimedOut(millis(), CMD_WATCHDOG_TIMEOUT_MS)) {
        v_target = 0.0f;
        w_target = 0.0f;
        base_motion_active = false;
        velocityCmd.reset();
        pidL.reset();
        pidR.reset();
        motorL.stop();
        motorR.stop();
        return;
    }

    if (fabs(v_target) < 0.01f && fabs(w_target) < 0.01f) {
        pidL.reset();
        pidR.reset();
    }

    const float w_cmd = w_target;

    velocityCmd.setTarget(v_target, w_cmd);
    velocityCmd.update(dt);

    float omegaLt = 0.0f, omegaRt = 0.0f;
    velocityCmd.getWheelTargets(omegaLt, omegaRt);

    const int32_t dL = last_dL_ctrl;
    const int32_t dR = last_dR_ctrl;

    const KinematicsInput kinIn{ dL, dR, dt };
    const KinematicsOutput kinOut = kinematics.update(kinIn);

    float pwmL = pidL.update(omegaLt, kinOut.omega_left, dt);
    float pwmR = pidR.update(omegaRt, kinOut.omega_right, dt);

    pwmL *= WHEEL_TRIM_L;
    pwmR *= WHEEL_TRIM_R;

    motorL.setPWM((int)pwmL);
    motorR.setPWM((int)pwmR);
}
