#include "RailTeleop.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <std_msgs/Float64.h>

RailTeleop::RailTeleop(){
    _nh.setCallbackQueue(&_queue);
    ros::NodeHandle pnh("~");
    pnh.param("rail_speed", _speed, 0.1);
    pnh.param("rail_lower", _lower, -0.52);
    pnh.param("rail_upper", _upper, 0.52);
    pnh.param("rail_calib_pos", _calibPos, _lower);
    _calibPos = std::min(std::max(_calibPos, _lower), _upper);
    _pub = _nh.advertise<std_msgs::Float64>("/z1_gazebo/rail_controller/command", 1);
    // Start from the carriage's current position so the jog never makes it jump.
    // joint_states only arrives once Gazebo is running (not paused).
    _sub = _nh.subscribe("/z1_gazebo/joint_states", 1, &RailTeleop::_jointStateCallback, this);
    _last = std::chrono::steady_clock::now();
}

void RailTeleop::_jointStateCallback(const sensor_msgs::JointState::ConstPtr& msg){
    if(_mode != Mode::WAITING) return;
    auto it = std::find(msg->name.begin(), msg->name.end(), "rail_joint");
    size_t i = it - msg->name.begin();
    if(it != msg->name.end() && i < msg->position.size()){
        _target = std::min(std::max(msg->position[i], _lower), _upper);
        _mode = Mode::ON;
        std::cout << "[rail] keyboard jog on: hold x = +x, z = -x (" << _speed
                  << " m/s, " << _lower << " .. " << _upper << " m), carriage at "
                  << _target << " m; calibration (=) sends it to " << _calibPos << " m"
                  << std::endl;
    }else{
        _mode = Mode::OFF;   // plain z1.launch: no rail in this model
        std::cout << "[rail] no rail_joint in /z1_gazebo/joint_states, rail jog off" << std::endl;
    }
    _sub.shutdown();
}

void RailTeleop::_publish(){
    std_msgs::Float64 msg;
    msg.data = _target;
    _pub.publish(msg);
}

void RailTeleop::update(double direction){
    auto now = std::chrono::steady_clock::now();
    double dt = std::chrono::duration<double>(now - _last).count();
    _last = now;
    if(_mode == Mode::WAITING) _queue.callAvailable();
    if(_mode == Mode::OFF) _homeRequested = false;
    if(_mode != Mode::ON) return;   // a home request made while WAITING is kept

    if(_homeRequested.exchange(false)){
        _homing = true;
        std::cout << "[rail] calibration: moving to " << _calibPos << " m" << std::endl;
    }

    if(direction != 0.0){
        if(_homing){
            _homing = false;
            std::cout << "[rail] calibration move cancelled by jog" << std::endl;
        }
        double next = _target + (direction > 0 ? 1.0 : -1.0) * _speed * dt;
        next = std::min(std::max(next, _lower), _upper);
        if(next != _target){
            _target = next;
            _publish();
        }
        _moving = true;
        return;
    }
    if(_moving){
        _moving = false;
        std::cout << "[rail] target " << _target << " m" << std::endl;
    }
    if(_homing){
        double step = _speed * dt;
        double err = _calibPos - _target;
        _target = (std::abs(err) <= step) ? _calibPos : _target + (err > 0 ? step : -step);
        _publish();
        if(_target == _calibPos){
            _homing = false;
            std::cout << "[rail] at calibration position " << _calibPos << " m" << std::endl;
        }
    }
}
