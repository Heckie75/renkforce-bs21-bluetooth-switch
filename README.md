# renkforce-bs21-bluetooth-switch
Full-features shell script in order to manage Renkforce's BS-21 bluetooth switch and timer 

The Renkforce BS-21 is a remote 230V switch. It was sold by Conrad Elektronic in Germany a few years ago. For details take a look at [Amazon](https://www.amazon.de/Renkforce-Bluetooth-Funk-Steckdose-Innenbereich-BS-21/dp/B00PH8XF70)

In comparison to many remote switches which use the 433MHz band the BS-21 is based on bluetooth v2.1. The advantage is that there is no need to have additional senders and receivers connected via GPIO. Since I want to use an Intel NUC as a home server instead of a Raspberry Pi, the BS-21 was my first choice. The NUC doesn't have GPIO pins. USB 433MHz dongles doesn't seem to be available. Another advantage is that you get the real state of the power switch since bi-directional communication is supported. 

The BS-21 has typical features of a timeclock:
* 20 power-on timers and 20 power-off timers which can be individually assigned to weekdays
* random mode which turns power on and off in defined period
* countdown mode in order to switch power on or off after certain period 
* internal clock. However, quality seems to be poor. The clock has a difference between 2 and 5 minutes per day!

The BS-21 requires explicit pairing and is secured by pin so that your neighbour can't take control.

For official Renkforce BS-21 manual visit [Conrad](http://www.produktinfo.conrad.com/datenblaetter/1200000-1299999/001208452-an-01-ml-BLUETOOTH_SCHALTSTECKDOSE_BS_21_de_en.pdf)

## Getting started
Before you can use the power switch it is required to perform bluetooth pairing. In order to pair the switch it must be in pairing mode which is the case after
*  the switch has been plugged
*  the switch has been set into pairing mode, e.g. by an other device which has already been paired.

In both cases the pairing mode runs just for 2 minutes so that you must hurry up.

After you have set the switch into pairing mode, you can start scanning and pairing by using `bluetoothctl`

```
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
[BS-21-001514-0-A]# quit
```

## Aliases
For convenience reasons I recommend to use aliases. Instead of entering the mac address and pin each time you want to run the script, you can call the script by using meaningful names. 

The script tries to read a file called `.known_bs21` which must be located in your home folder. It is a text file with three columns:
1. MAC address
2. PIN
3. Meaningful name

My `.known_bs21` looks as follows:
```
$ cat ~/.known_bs21
5C:B6:CC:00:1F:5A   1234    Printer
5C:B6:CC:00:28:38   1234    Coffeemachine
```

This enables you to call the script like this
```
$ bs21.py Coffee -on
```

instead of 
```
$ bs21.py 5C:B6:CC:00:28:38 1234 -on
```

## Basic commands
### Get help
In order to get an overview of the full feature set enter the following:
```
$ bs21 -help
 Renkforce BS-21 bluetooth power switch command line interface for Linux / Raspberry Pi

 USAGE:   bs21.py <mac> <pin> <command1> <params1> <command2> ...
 EXAMPLE: sync time and power on
          $ ./bs21.py 5C:B6:CC:00:1A:AE 1234 -sync -on
        
 -clear-all                      	clears alls timers, random mode and countdown
 -countdown <hh:mm:ss> <on|off>     starts countdown with action (turn on / turn off) and duration
 -countdown-clear                	resets countdown
 -countdown-until <hh:mm> <on|off>	starts countdown with action (turn on / turn off) and specific endtime
 -debug                          	prints raw data sent and received
 -json                           	prints information in json format
 -off                            	power switch off
 -on                             	power switch on
 -pin <nnnn>                     	set new pin with 4-digits
 -random <mtwtfss> <hh:mm> <hh:mm>	activated random mode with daymask, e.g. MTWTFss for Monday to Friday, starttime und duration
 -random-clear                   	stops random mode
 -sleep <nnn>                    	script sleeps for n seconds and stays connected. Helpful for queueing commands
 -status                         	just read and print the basic information of the bluetooth switch
 -sync                           	synchronizes current time with your computer
 -timer <n:1-20> <on|off> <mtwtfss> <hh:mm>	sets specific timer (1-20) with action (turn on / turn off), daymask, e.g. MTWTFss for Monday to Friday, starttime
 -timer-clear <n:1-20> <on|off>  	resets specific timer
 -timers                         	prints all timer information
 -toggle                          toggles switch
 -visible                        	make bluetooth switch visible for a while so that it can be discovered by bluetooth services
 ```

You get specific help for a command if you ask for it explicitly:
```
$ bs21 -help on

 -on                             	power switch on
```

You get also help in case of any mistake:
```
$ bs21 -timer-clear

  ERROR: Please check parameters of command

 -timer-clear <n:1-20> <on|off>  	resets specific timer
```

### Turn switch on and off and get status

You can turn on your switch as follows:
```
$ bs21.py 5C:B6:CC:00:20:68 1234 -on
```

You can also use an alias and leave pin out if you have provided it in `~/.known_bs21` :
```
$ bs21.py Coffeemachine -off
```

You can also toggle the switch by using the `-toggle` command.

**Note**: 
You don't even have to write the whole alias. This works as well:
```
$ bs21.py Coffee -off
```

Now let's read the status of the switch:
```
$ bs21.py Coffee -status

 MAC-Address:      5C:B6:CC:00:20:68
 PIN:              1234
 Alias:            Coffeemachine

 Model:            BS-21
 Serial no.:       001514
 Firmware:         V1.17

 Relais:           on
 Random mode:      off
 Countdown:        off
 Power:            no
 Over temperature: no

 Time:             Sat, 09:03:28
 ```

## Change pin
Maybe you want to change the PIN of the device now:
```
$ bs21.py Coffee -pin 0815
```

**Important:**
The script does NOT update the alias file `~/.known_bs21`. That's why you will get an error if you haven't updated the pin in this file manually:
```
$ bs21.py Coffee -status

 ERROR: Device has explicitly responded with error! Do you want to double-check PIN?
```

## Sync time
 The internal clock of the bluetooth switch is very poor. I have seen differences between 2 and 5 minutes per day. You should synchronize the time frequently. Actually I have setup a cron-job which synchronizes the device a few times per day. 

 Synchronization works like this.
 ```
 $ bs21.py Coffee -sync
 ```
 
## Countdown
You can start a countdown which turns the switch on or off after the given time. 

You can pass a duration (hh:mm:ss) after the switch will turn on or off:
```
$ bs21.py Coffee -countdown 00:10:00 off
```
*Note that the script will NOT toggle the switch, so that in this example it is assumed that the switch is already turned on.*

You can also specify a time instead of passing a duration:
```
$ bs21.py EndOfWorkSiren -countdown-until 16:55 on
```

You can query the remaining time of the countdown by using `-timers`:
```
$ bs21.py EndOfWorkSiren -timers
 Countdown:        Running, switch on in 07:26:04
```

Call `-countdown-clear` in order to resets countdown.
 
## Random mode
Start random mode by passing the day mask, starting time and duration. 
```
$ bs21.py Light -random mtwtfSs 9:30 2:00
```
In this example random mode will be set for Saturday at 9:30 for 2:00 hours. The day mask is compiled by the first letter for every day. Capital letters indicate that timer will be set for this day. 

Random mode can be stopped by calling `-random-clear`

## Timers
The bluetooth switch has 40 timer slots: 20 for turning power on and another 20 for turning power off. On and off timers are totally independent. 

Program a timer for starting your coffeemachine from Monday to Friday at 7:10 a.m.
```
$ bs21.py Coffee -timer 1 on MTWTFss 7:10
```

Don't forget to turn coffeemachine off afterwards:
```
$ bs21.py Coffee -timer 1 off MTWTFss 7:20
```

At weekend I would like to have coffee at 8:00 a.m.
```
$ bs21.py Coffee -timer 2 on mtwtfSS 8:00
$ bs21.py Coffee -timer 2 off mtwtfSS 8:10
```

Please notice the day mask. The day mask is compiled by the first letter for every day. Capital letters indicate that timer will be set for this day. 

Let's take a look at the timers that we have set so far:
```
$ bs21.py Coffee -timers
 Timer 01:         Switch on at 07:10 on Mon, Tue, Wed, Thu, Fri
 Timer 02:         Switch on at 08:00 on Sat, Sun
 Timer 01:         Switch off at 07:16 on Mon, Tue, Wed, Thu, Fri
 Timer 02:         Switch off at 08:10 on Sat, Sun
```

You can clear a specific timer as follows:
```
$ bs21.py Coffee -timer-clear 2
```
 
Last but not least you can clear all schedules, i.e. timers, random mode and countdown by calling `-clear-all`.
```
$ bs21.py Coffee -clear-all
```

## Command queueing
Sometimes you want to pass more than one command to the bluetooth switch. Since the bluetooth connection initialization takes often a few seconds the connection is initialized once at the beginning and closed at the very end of the queue. 

The script allows command queueing:
```
USAGE:   bs21.py <mac> <pin> <command1> <params1> <command2> ..
```

For example, sometime I would like to start the coffeemachine and run it for 10 minutes. In addition I would like to synchronize the clock because I expect that it is wrong again. 
```
$ bs21.py Coffee -on -sync -countdown 00:10:00 off
```
* Step 1 is to turn coffeemachine on
* Step 2 is to synchronize time
* Step 3 is to set countdown for 10 minutes which turns switch off.

There is a special command called `-sleep`. This can be used in order to pause the command queue for a couple of seconds, e.g.
```
$ bs21.py Light -on -sleep 1 -off -sleep 1 -on -sleep 1 -off
```

## Advanced features
If you want to set the bluetooth switch in visible mode so that it can be discovered by other hosts call the follows:
```
$ bs21.py Light -visible
```

If you want to get the full status and timer information in JSON format call this:
```
$ bs21.py Light -json
{
  "status": {
    "countdown": true, 
    "on": false, 
    "random": false, 
    "power": false, 
    "overtemp": false, 
    "model": "BS-21", 
    "firmware": "V1.17", 
    "serial": "001514"
  }, 
  "random": {
    "slot": 41, 
    "active": false, 
    "duration": "02:00:00", 
    "schedule": {
      "weekday": [
        "Sat"
      ], 
      "time": "09:30:00"
    }
  }, 
  "countdown": {
    "slot": 43, 
    "remaining": "07:02:37", 
    "active": true, 
    "elapsed": "00:23:36", 
    "type": "on", 
    "original": "07:26:13"
  }, 
  "timers": [
    {
      "slot": 1, 
      "type": "on", 
      "schedule": {
        "weekday": [], 
        "time": "00:00:00"
      }
    }, 
/* 2, 3, ..., 39 */
    {
      "slot": 40, 
      "type": "off", 
      "schedule": {
        "weekday": [], 
        "time": "00:00:00"
      }
    }
  ], 
  "time": {
    "weekday": [
      "Sat"
    ], 
    "time": "09:52:20"
  }, 
  "device": {
    "alias": "Light", 
    "mac": "5C:B6:CC:00:20:68", 
    "pin": "1234"
  }
}
```
 
 Last but not least. If you want to see what's going over the air, take a look at the raw data that is passed between host and bluetooth switch by putting the `-debug` command in front of all other commands, e.g.:
```
$ bs21 Coffee -debug -sync -on -countdown 00:10:00 off
 SEND: synchronize time
 > TIME 20 09 56 12#1234
 < $BS-21-001514-0-Q V1.17 20 09 56 12
 SUCCESS: time synchronized
 SEND: turn on
 > REL1#1234
 < $BS-21-001514-1-Q V1.17 20 09 56 12
 SUCCESS: turned on
 SEND: set countdown
 > SET43 00 00 10 00 01#1234
 < $OK|SET43 00 00 10 00 01#1234|SET43 00 00 10 00 16
 SUCCESS: countdown set
 ```

Have a lot of fun!