#ifndef RAIL_TELEOP_H
#define RAIL_TELEOP_H

#include <atomic>
#include <chrono>
#include <ros/ros.h>
#include <ros/callback_queue.h>
#include <sensor_msgs/JointState.h>

// Keyboard jog for the 7th-axis rail (z1_ext_gazebo/launch/z1_rail.launch).
// Integrates a -1/0/+1 key direction into a carriage target and publishes it to
// /z1_gazebo/rail_controller/command (std_msgs/Float64, metres).
// requestHome() (called when the arm enters calibration) ramps the carriage to
// rail_calib_pos (default: the left end, rail_lower).
class RailTeleop{
public:
    RailTeleop();
    // direction: +1 / -1 while a jog key is held, 0 otherwise. Call periodically.
    void update(double direction);
    // Thread-safe; may be called from the FSM thread.
    void requestHome(){_homeRequested = true;}
private:
    enum class Mode{WAITING, ON, OFF};
    void _jointStateCallback(const sensor_msgs::JointState::ConstPtr& msg);
    void _publish();

    ros::CallbackQueue _queue;   // own queue: IOROS's spinOnce() never runs our callback
    ros::NodeHandle _nh;
    ros::Subscriber _sub;
    ros::Publisher _pub;
    Mode _mode = Mode::WAITING;
    double _target = 0.0;
    double _speed;            // m/s
    double _lower, _upper;    // m, same as rail_joint limits in z1_on_rail.xacro
    double _calibPos;         // m, where calibration sends the carriage
    bool _moving = false;     // a jog key was held on the previous update
    bool _homing = false;     // automatic move to _calibPos in progress
    std::atomic<bool> _homeRequested{false};
    std::chrono::steady_clock::time_point _last;
};

#endif
