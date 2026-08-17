uint8 SAFE=0
uint8 OBSTACLE=1
uint8 MANUAL=2
uint8 ESTOP=3
uint8 SENSOR_STALE=4

builtin_interfaces/Time stamp
uint8 state
bool motion_allowed
bool estop_active
bool manual_mode
bool obstacle_active
float32 obstacle_distance_m
string reason
