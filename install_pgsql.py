import sys, ipaddress, subprocess, os

################# run from this directory (where sript is located)
arg = sys.argv[1]

if arg == "--help":
    print('Usage: python ./install_pgsql.py "x.x.x.x, x.x.x.x"\n\nThis script chooses a least loaded server from given ones\nand installs PostgreSQL on it, then we are going to configure it a little...\n\n\nScript thinks the two servers already have SSH pub keys (user root) (and your user has the SSH private key), so please do not let it down\nEnter two comma-separated IP addresses of servers')
    exit()

if len(sys.argv) != 2 or arg.count(",") != 1:
    print('Usage: python install_pgsql.py "x.x.x.x, x.x.x.x"')
    exit()


server1 = arg.split(",")[0].strip()
server2 = arg.split(",")[1].strip()


print("Checking if IP addresses are valid...")

try:
    ipaddress.ip_address(server1)
    ipaddress.ip_address(server2)
    print("IP addresses are valid")
except:
    print("IP addresses are not valid, please type real IPs of your services")
    print('Usage: python ./install_pgsql.py "x.x.x.x, x.x.x.x"')
    exit()


print("Checking if hosts are available...")

if os.system(f"ping {server1} -c 4 -W 4 > /dev/null") or os.system(f"ping {server2} -c 4 -W 4 > /dev/null"):
    print("One or both of hosts unreachable")
    exit()
else:
    print("Hosts are available, processing...")


print("Checking Internet connection...")
for server in (server1, server2):
    if os.system(f"ssh root@{server} 'ping -c 4 -W 4 ya.ru' > /dev/null") or os.system(f"ssh root@{server} 'ping -c 4 -W 4 google.com' > /dev/null"):
        if os.system(f"ssh root@{server} 'ping -c 4 -W 4 8.8.8.8' > /dev/null"):
            print(f"Some problems with Internet connection, cannot ping ya.ru or google.com on server {server}")
            exit()
        print(f"Some problems with DNS: can ping 8.8.8.8 but cannot ping ya.ru or google.com on server {server}")
        exit()
print("Done")

print("Checking servers' load for last 15 minutes")

server1_cores = int(subprocess.check_output(f"ssh root@{server1} lscpu" + " | grep '^CPU(s):' | awk '{print $2}'", shell=True).decode("utf-8").split()[-1].replace(",","."))
server2_cores = int(subprocess.check_output(f"ssh root@{server2} lscpu" + " | grep '^CPU(s):' | awk '{print $2}'", shell=True).decode("utf-8").split()[-1].replace(",","."))
server1_load = float(subprocess.check_output(f"ssh root@{server1} uptime", shell=True).decode("utf-8").split()[-1].replace(",","."))/server1_cores
server2_load = float(subprocess.check_output(f"ssh root@{server2} uptime", shell=True).decode("utf-8").split()[-1].replace(",","."))/server2_cores


least_loaded_server = server2 if server1_load > server2_load else server1
other_server = server2 if least_loaded_server == server1 else server1
least_loaded_server_os = "deb" if subprocess.check_output(f"ssh root@{least_loaded_server} \"hostnamectl | grep -i debian || true\"", shell=True).decode("utf-8") != "" else "centos"
other_server_os = "deb" if subprocess.check_output(f"ssh root@{other_server} \"hostnamectl | grep -i debian || true\"", shell=True).decode("utf-8") != "" else "centos"

print(f"\nLoad of server1 is {server1_load}, load of server2 is {server2_load}, choosing {'server2' if server1_load > server2_load else 'server1'} (OS: {'Debian' if least_loaded_server_os == 'deb' else 'CentOS'})\n")

os.system("rm -rf roles")
os.system("cp -rf roles_template roles")

os.system(f"sed -i 's/__least_loaded_server__/{least_loaded_server}/g' roles/pg_install_{least_loaded_server_os}/vars/main.yaml")
os.system(f"sed -i 's/__other_server__/{other_server}/g' roles/pg_install_{least_loaded_server_os}/vars/main.yaml")


print("Prepare inventory for ansible")

os.system(f"echo -e 'ansible_user=root\n\npg_server    ansible_host={least_loaded_server}\nother_server    ansible_host={other_server}' > inventory")

print("Done\nAll preparations are done, now going to run ansible playbook...")

if os.system(f"ansible-playbook pg_install_{least_loaded_server_os}.yaml -i inventory -T 5 -u root"):
    exit()

print("Installation done, trying to connect to pgsql server from the other host...")
other_server_packet_manager = "apt-get" if other_server_os == "deb" else "dnf"
if os.system(f"ssh root@{other_server} '{other_server_packet_manager} install -y postgresql' > /dev/null"):
    print("Failed while trying to install postgresql package on host without pgsql server")
    exit()
select_test = os.system(f"ssh root@{other_server} 'PGPASSWORD=student psql -U student -h {least_loaded_server} -d postgres -c \"SELECT 1;\"' > /dev/null")
print(f"\nTrying statement SELECT 1: {'Success' if not select_test else 'Failed'}\n")
print(f"{'PostgreSQL Server is successfully installed' if not select_test else 'Failed to install PostgreSQL Server'}")
