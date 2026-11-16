# Z1 arm simulation setup (Gazebo)

Unitree's official Z1 sim uses **ROS 1 Noetic + Gazebo Classic 11** (not the newer
"Gazebo Sim"). Noetic only supports Ubuntu 20.04, so on this Arch/Omarchy host it
runs in a Docker container that shows its windows on the desktop.

How the pieces connect:

    z1_sdk examples ──UDP 127.0.0.1:8071──▶ sim_ctrl ──ROS topics──▶ Gazebo (Z1 model)
                                           (z1_controller/sim)   /z1_gazebo/JointXX_controller/{command,state}

`sim_ctrl` is the same controller as `z1_ctrl`. The only difference is that it sends
motor commands to Gazebo over ROS instead of to the real arm over UDP. SDK code works
with it unchanged.

## One-time setup (host)

1. Install Docker, start it, and add yourself to the `docker` group:

       sudo pacman -S --needed docker xorg-xhost
       sudo systemctl enable --now docker
       sudo usermod -aG docker $USER

   The `docker` group lets you use Docker without sudo. `xorg-xhost` lets
   containers open windows on the desktop.

2. **Reboot** (logging out is not enough on Omarchy). Then check:
   - `groups` → includes `docker`
   - `docker info >/dev/null && echo ok` → `ok`

   Logging out only restarts Hyprland. The systemd user session keeps the old group
   list, so new terminals still lack `docker`. `newgrp docker` is a temporary fix
   for one shell.

## One-time setup (container)

3. Allow containers to use the display (needed again after every login):

       xhost +SI:localuser:root

   Gazebo is a GUI app. Hyprland's XWayland exposes an X11 socket, and `xhost`
   lets local containers connect to it.

4. Create and enter the container:

       docker run -it --name z1sim \
         --net=host --ipc=host \
         -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
         -v /tmp/.X11-unix:/tmp/.X11-unix \
         --device /dev/dri \
         -v ~/Desktop/projects/z1_ext:/z1_ext \
         osrf/ros:noetic-desktop-full bash

   - The image is Ubuntu 20.04 with ROS Noetic and Gazebo 11 preinstalled.
   - `--net=host`: UDP port 8071 is the same inside and outside the container.
   - `--device /dev/dri`: GPU rendering on Intel/AMD. On NVIDIA, also install
     `nvidia-container-toolkit` and add `--gpus all`.
   - `-v …:/z1_ext`: the repo is shared, so edits on the host appear in the
     container immediately.

   If the name `z1sim` is already taken, use `docker start -ai z1sim` or remove the
   old container with `docker rm z1sim`.

5. Install the extra ROS packages (inside the container):

       apt update && apt install -y git ros-noetic-ros-control ros-noetic-ros-controllers \
         ros-noetic-gazebo-ros-control ros-noetic-joint-state-controller \
         ros-noetic-effort-controllers libeigen3-dev libboost-dev

   The Z1 model loads its joint controllers through `ros_control`, which
   `desktop-full` doesn't include. Eigen and Boost are needed to build `z1_controller`.

6. Build Unitree's Gazebo packages in a catkin workspace:

   a. Clone the Gazebo packages:

          mkdir -p ~/catkin_ws/src && cd ~/catkin_ws/src
          git clone https://github.com/unitreerobotics/unitree_ros.git

      `unitree_ros` provides:
      - `z1_description`: the URDF and meshes.
      - `unitree_gazebo`: the world and `z1.launch`.
      - `unitree_legged_control`: the Gazebo plugin that acts like the Z1 motors and
        takes `MotorCmd` messages (q, dq, tau, Kp, Kd).

   b. Add the message definitions. **This is required**, because `unitree_ros`
      doesn't include them:

          git clone https://github.com/unitreerobotics/unitree_ros_to_real.git
          mv unitree_ros_to_real/unitree_legged_msgs . && rm -rf unitree_ros_to_real

      `unitree_legged_control` is compiled against `unitree_legged_msgs` (the
      `MotorCmd`/`MotorState` types). Only that folder is kept; the rest of
      `unitree_ros_to_real` is real-robot code you don't need. Without it,
      `catkin_make` skips the controller plugin, but Gazebo still launches. The arm
      then hangs limp with `Could not load class … UnitreeJointController` errors
      (see Troubleshooting).

   c. Build. Do a clean build so nothing stale is left from an earlier failed attempt:

          cd ~/catkin_ws && rm -rf build devel
          source /opt/ros/noetic/setup.bash
          catkin_make 2>&1 | tee ~/catkin_build.log

      The build must end at `[100%]` with no `Error`. If it doesn't, run
      `grep -n -i error ~/catkin_build.log` to find the first error.

   d. Source the workspace (now and in every future shell):

          echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc && source ~/.bashrc

      Sourcing `devel/setup.bash` tells ROS where these packages and compiled
      libraries are.

   e. Check that the controller plugin was built:

          ls ~/catkin_ws/devel/lib | grep unitree     # must list libunitree_legged_control.so

      If it isn't listed, the joint controllers won't load and the arm won't move.

7. Build `sim_ctrl`:

       cd /z1_ext/z1_controller && mkdir -p build_sim && cd build_sim
       cmake .. && make -j$(nproc)

   `CMakeLists.txt` only builds `sim/` when ROS (catkin) is found, which is true
   inside the container. The separate `build_sim/` folder avoids clashing with the
   host's `build/` CMake cache.

8. (Optional) Build the SDK examples for the sim:

       cd /z1_ext/z1_sdk && mkdir -p build_sim && cd build_sim
       cmake .. && make -j$(nproc)

## Every session

9. On the host: `xhost +SI:localuser:root`, then `docker start -ai z1sim`.
   Open more shells with `docker exec -it z1sim bash`.

    Steps 10–12 all run in container shells (prompt `root@…:/#`), not in host terminals.

10. Terminal 1: start Gazebo with the Z1:

        roslaunch unitree_gazebo z1.launch

    This starts roscore and Gazebo, opens the Gazebo window, spawns the arm, and
    loads one controller per joint plus the gripper. Wait for the line

        Started controllers: joint_state_controller, Joint01_controller, … gripper_controller

    If it lists only `joint_state_controller`, the plugin is missing; go back to step 6.
    If the sim is paused, press Play (bottom left). Check with
    `rostopic list | grep command` (it should show 7 `…/command` topics).

    You can ignore these warnings: `aliengoZ1_description` naming,
    `gripperStator` non-unique name, and `amdgpu os_same_file_description`.
    `gzclient` is needed by hand only if no window appeared.

11. Terminal 2: start the controller. Gazebo must already be running:

        cd /z1_ext/z1_controller/build_sim
        ./sim_ctrl k    # keyboard mode
        ./sim_ctrl      # SDK mode (listens on 127.0.0.1:8071)

    Keyboard mode (this terminal must be focused):
    - `` ` ``: back to start pose.
    - `2`: joint control (q/a, w/s, e/d, r/f, t/g, y/h move joints 1–6).
    - `3`: Cartesian control.
    - `1`: passive.
    - `=`: calibration. In the rail sim it also sends the carriage to the left end (−0.52 m).
    - `x` / `z` (hold): move the 7th-axis carriage +x / −x (rail sim only, see below).

12. Terminal 3 (SDK mode only): run an example:

        cd /z1_ext/z1_sdk/build_sim && ./highcmd_basic

    The SDK talks to `sim_ctrl` exactly as it talks to `z1_ctrl` on the real arm, so
    the same code runs on the hardware.

## Z1 on the 7th-axis rail (optional)

`z1_ext_gazebo/` is a catkin package that puts the arm on the 7th-axis rail from
`cad/whole12.zip`, with the parts unpacked in `cad/whole12/`. The carriage slides on a
prismatic joint, `rail_joint` (x axis, ±0.52 m, which is where the runners reach the
hard stops), and the arm rides on the carriage's steel plate.

One time (in the container), link it into the workspace and rebuild:

    ln -s /z1_ext/z1_ext_gazebo ~/catkin_ws/src/
    cd ~/catkin_ws && catkin_make && source devel/setup.bash

Then use this instead of step 10:

    roslaunch z1_ext_gazebo z1_rail.launch

`Started controllers:` must now also list `rail_controller`. Steps 11 and 12 are
unchanged: the model is still named `z1_gazebo`, so `sim_ctrl` finds it.
Keyboard control of the carriage is in `sim_ctrl k` (rebuild it after pulling: step 7).
Hold `x` to move +x and `z` to move −x, at 0.1 m/s, stopping at ±0.52 m. It works in
every arm state, with the arm keys unchanged. At startup it waits for Gazebo's
`/z1_gazebo/joint_states` and starts from the carriage's current position. It prints
`[rail] keyboard jog on …` when ready; on plain `z1.launch` it prints `rail jog off`.
To change the speed or limits, set them before starting `sim_ctrl`, e.g.
`rosparam set /z1_controller/rail_speed 0.2` (also `rail_lower`, `rail_upper`, in m).
Entering calibration (`=`) moves the carriage, at the same speed, to `rail_calib_pos`
(default: `rail_lower`, the left end). It moves only if the arm really enters calibration.
Holding `x` or `z` during that move cancels it. `[rail] at calibration position` is
printed when the carriage arrives.
SDK mode doesn't drive the rail. There, or from any other shell, command it directly (metres):

    rostopic pub -1 /z1_gazebo/rail_controller/command std_msgs/Float64 "data: 0.3"
    rostopic echo -n1 /z1_gazebo/joint_states    # rail_joint position

How it was built: the parts in `cad/whole12/` are in their own frames.
`cad/whole12_placements.json` says where each copy sits in the assembly, and it
rebuilds `00_full_assembly.stl` triangle for triangle (`cad/tools/verify_placements.py`).
`z1_ext_gazebo/urdf/rail.xacro` is generated from it by `cad/tools/gen_rail_xacro.py`.
`urdf/z1_on_rail.xacro` is Unitree's `robot.xacro` with only the base joint changed.

Notes:
- `15_brake_block.stl` isn't used in `00_full_assembly.stl`, so it isn't in the model.
- Visual only (no collision): the runners (they would drag on the rails), the pinion,
  and the carriage-side drag-chain block. In the CAD, at every rail position, the
  chain block cuts into rail #1 (~1140 mm³), and the lower pinion disc and one pin
  cut into rail strip #0 (~734 mm³). Fix these in CAD if they're real.
- The pinion is rigid on the carriage (it doesn't spin), and there is no motor model.
- Masses use assumed materials (aluminium, steel plate/rack/pinion, MDF board), so
  `rail_controller` gains (p 2000, d 250) and the 200 N effort limit are starting values.

## Troubleshooting

- `permission denied … docker.sock`: the shell lacks the `docker` group. Reboot (step 2).
- `cannot open display` / `Authorization required … Aborted`: run `xhost +SI:localuser:root` on the host. `echo $DISPLAY`
  inside the container must not be empty.
- Black or slow Gazebo window: the GPU wasn't passed through. Check `--device /dev/dri`
  (or the NVIDIA setup in step 4).
- `libZ1_x86_64.so: cannot open shared object file` / `cd /z1_ext…: not found`:
  you're in a host terminal. Steps 5–12 run **inside the container**
  (`docker exec -it z1sim bash`). `sim_ctrl` was built there and looks for its
  libraries under `/z1_ext/...` and `/opt/ros/noetic`, which only exist in the
  container.
- `Could not load class 'unitree_legged_control/UnitreeJointController'` in the
  `roslaunch` output, and the arm doesn't move with `sim_ctrl`: the controller plugin
  library was never compiled, so `sim_ctrl`'s commands go unanswered. Do step 6b
  (add `unitree_legged_msgs`), then 6c–6e (clean rebuild and check), then relaunch.
- Arm goes limp or doesn't move, with no errors: `sim_ctrl` started before Gazebo,
  or the sim is paused.
- Don't run `chmod 666 /var/run/docker.sock`: it gives every user root-level access.
