# renkforce-bs21-bluetooth-switch
Full-features shell script in order to manage Renkforce's BS-21 bluetooth switch and timer 

The Renkforce BS-21 is a remote 230V switch. It was sold by Conrad Elektronic in Germany a few years ago. For details take a look at [Amazon](https://www.amazon.de/Renkforce-Bluetooth-Funk-Steckdose-Innenbereich-BS-21/dp/B00PH8XF70)

In comparison to many remote switches which use a 433MHz connection the BS-21 is based on bluetooth v2.1. The advantage is that there is no need to have additional senders and receivers connected via GPIO. Since I want to use an Intel NUC as home server instead of a Raspberry Pi, the BS-21 is my first choice. The NUC doesn't have GPIO pins and USB 433MHz dongles doesn't seem to be available. An other advantage is that you get the real state of the power switch since it isn't a one-direction communication. 

The BS-21 has typical features of a timeclock:
* Explicit pairing and secured by pin so that other users or your neighbour can't take control 
* 20 power-on timers and 20 power-off timers which can be individually assigned to weekdays
* random mode which turns power on and of in defined period
* countdown mode in order to switch power on or off after certain time period 
* internal clock. However, quality seems to be poor. The clock has a difference between 2 and 5 minutes per day!

For manual visit [Conrad](http://www.produktinfo.conrad.com/datenblaetter/1200000-1299999/001208452-an-01-ml-BLUETOOTH_SCHALTSTECKDOSE_BS_21_de_en.pdf)

## Getting started

Before you can use the power switch it is required to perform bluetooth pairing. In order to pair the switch it must be in pairing mode which is the case after
*  the switch has been plugged
*  the switch has been set into pairing mode e.g. by the official app or another system which has already been paired

In both cases the pairing mode runs just for 2 minutes so that you must be fast.

After you have set the switch into pairing mode, you can start scanning and pairing by using ˋbluetoothctlˋ

ˋˋˋ
$ bluetoothctl

[bluetooth]# agent on
Agent registered

[bluetooth]# scan on
Discovery started

[NEW] Device 5C:B6:CC:00:20:68 BS-21-001514-0-A

[bluetooth]# pair 5C:B6:CC:00:20:68

Attempting to pair with 5C:B6:CC:00:20:68
[CHG] Device 5C:B6:CC:00:20:68 Connected: yes
Request confirmation
[agent] Confirm passkey 136654 (yes/no): yes
[CHG] Device 5C:B6:CC:00:20:68 UUIDs: 00001101-0000-1000-8000-00805f9b34fb
[CHG] Device 5C:B6:CC:00:20:68 UUIDs: 00001200-0000-1000-8000-00805f9b34fb
[CHG] Device 5C:B6:CC:00:20:68 Paired: yes
Pairing successful
[BS-21-001514-0-A]#
ˋˋˋ

## Aliases
For convenience I recommend to make use a aliases. Instead of entering the mac address and pin each time, you can call the script by using meaningful device names. 

The script tries to read a file called ˋ.known_bs21ˋ in your home folder. It is a text file with three columns:
1. MAC address
2. PIN
3. Meaningful name

My file looks as follows:
ˋˋˋ
$ cat ~/.known_bs21
5C:B6:CC:00:1F:5A   1234    Printer
5C:B6:CC:00:28:38   1234    Coffeemachine
ˋˋˋ

This enables you to call the script like this
ˋˋˋ
$ bs21.py Coffee -on
ˋˋˋ

instead of 
ˋˋˋ
$ bs21.py 5C:B6:CC:00:28:38  1234 -on
ˋˋˋ

## Basic commands
### Get help
### Turn switch on 

## Change pin

## Command queueing

## Timers

## Countdown

## Random mode

## Advanced features