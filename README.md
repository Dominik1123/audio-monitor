# Audio Monitor

This program can be used to monitor the environment with a connected microphone.
The user interface is realized with the Telegram API and allows notifications
when the sound amplitude is too high.


## Setup

**Requirements:**

* The program records audio via the [`arecord`](http://manpages.ubuntu.com/manpages/xenial/man1/aplay.1.html) command line utility and encodes
  the resulting stream via [`opusenc`](http://manpages.ubuntu.com/manpages/xenial/man1/opusenc.1.html) - these two programs need to be available on the PATH.

**Setup:**

* The required packages can be installed via `pip install -r requirements.txt`.
* The configuration at `config.py` needs to be filled in.

Most default values in the configuration file should work without modification (`config.py` contains comments describing the details).

The `audio.device` value can be checked via `arecord -l`. The output should be something like this:

    **** List of CAPTURE Hardware Devices ****
    card 1: PCH [HDA Intel PCH], device 0: ALC3234 Analog [ALC3234 Analog]
      Subdevices: 1/1
      Subdevice #0: subdevice #0

In this case the device is located at `card 1, device 0` so the default value of `device='1,0'` is correct (adjust this value as needed).

The Telegram handler accepts the following commands, so the Telegram bot's command list should be updated accordingly:

* `/ping` -- asks the bot to say hello in order to verify it's still running
* `/threshold X` -- sets the notification threshold for sound amplitude to `X` (i.e. when the sound amplitude goes above `X` a notification is sent)
* `/listen X` -- requests a voice message containing the most recent `X` seconds of audio recording (if `X` is omitted then the full recording is sent)
* `/plot` -- requests a plot showing the sound amplitude maximum and mean value over time
* `/reset` -- clears all the data collected thus far


## Usage

Running `python main.py` starts the program and should immediately send a notification over Telegram. It's then ready to use.
In order to determine a sensible value for the notification threshold one should generate noise with a similar volume that is expected to be monitored.
With `/plot` the corresponding sound pressure which has been recorded can be checked and the notification threshold can be set via `/threshold X` accordingly.
