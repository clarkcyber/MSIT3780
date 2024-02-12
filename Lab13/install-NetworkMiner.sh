apt install mono-devel -y
wget https://www.netresec.com/?download=NetworkMiner -O /tmp/nm.zip
unzip /tmp/nm.zip -d /opt/
cd /opt/NetworkMiner*
chmod +x NetworkMiner.exe
chmod -R go+w AssembledFiles/
chmod -R go+w Captures/