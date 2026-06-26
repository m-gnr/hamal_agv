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
#include "src/motor/motor.h"
#include "src/comm/serial_comm.h"
#include "src/timing/timing.h"

// ======================================================
// OBJECTS
// ======================================================

SerialComm serial;

Encoder leftEncoder(ENC_L_A, ENC_L_B, ENC_L_DIRECTION);
Encoder rightEncoder(ENC_R_A, ENC_R_B, ENC_R_DIRECTION);

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

    Serial.println("Ready");
}

// ======================================================
// LOOP (Core 1)
// ======================================================
void loop() {
    serial.update();

    // --------------------
    // ENCODER SAMPLING (every loop)
    // --------------------
    static int32_t last_dL_ctrl = 0;
    static int32_t last_dR_ctrl = 0;

    // Accumulate ticks for telemetry (ENC_TX_DT_S window)
    static int32_t enc_accum_L = 0;
    static int32_t enc_accum_R = 0;

    const int32_t dL_step = leftEncoder.readDelta();
    const int32_t dR_step = rightEncoder.readDelta();

    // Control uses per-loop deltas
    last_dL_ctrl = dL_step;
    last_dR_ctrl = dR_step;

    // Telemetry sends summed ticks since last ENC publish
    enc_accum_L += dL_step;
    enc_accum_R += dR_step;

    // --------------------
    // SERIAL TX (MCU → ROS) - independent of control tick
    // Contract:
    //   $ENC,t_us,dl,dr*CS @ ENC_TX_DT_S
    //   $IMU,t_us,gz,ax,ay,az*CS @ IMU_TX_DT_S
    // --------------------
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

    // --------------------
    // CONTROL LOOP (100 Hz / CONTROL_DT_S)
    // --------------------
    if (!controlTimer.tick())
        return;

    const float dt = controlTimer.dt();

    static float v_target = 0.0f;
    static float w_target = 0.0f;

    if (serial.hasCmdVel()) {
        const CmdVel cmd = serial.getCmdVel();
        v_target = cmd.v;
        w_target = cmd.w;
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

    // Use per-loop encoder deltas for control (do NOT readDelta again)
    const int32_t dL = last_dL_ctrl;
    const int32_t dR = last_dR_ctrl;

    const KinematicsInput kinIn{ dL, dR, dt };
    const KinematicsOutput kinOut = kinematics.update(kinIn);

    const float pwmL = pidL.update(omegaLt, kinOut.omega_left, dt);
    const float pwmR = pidR.update(omegaRt, kinOut.omega_right, dt);

    motorL.setPWM((int)pwmL);
    motorR.setPWM((int)pwmR);
}