# Z1 arm setup

1. Mount the arm firmly; e-stop within reach.
2. Power the arm on; wait ~30 s for it to boot.
3. Connect Ethernet: arm → PC port `enp2s0` (`ip -br link` should show it UP).
4. Create the static network profile (one-time; no gateway, so Wi-Fi keeps internet):
       sudo nmcli con add type ethernet ifname enp2s0 con-name z1-arm \
         ipv4.method manual ipv4.addresses 192.168.123.162/24 \
         ipv4.never-default yes ipv6.method disabled \
         connection.autoconnect yes connection.autoconnect-priority 100
5. Bring it up: `sudo nmcli con up z1-arm`
6. Check:
   - `ip -br addr show enp2s0` → 192.168.123.162/24
   - `ip route get 192.168.123.110` → `dev enp2s0` (not wlp3s0)
   - `ping -c 3 192.168.123.110` → replies
7. Test: `cd z1_controller/build && sudo ./z1_ctrl k` → no "wait time out" warnings.
