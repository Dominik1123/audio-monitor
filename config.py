from argparse import Namespace


audio = Namespace(
    sample_rate=44100,  # [Hertz] - depending on the connected microphone (the default should be a sensible value).
    chunk_duration=3,   # [seconds] - audio is recorded and stored in chunks of that length.
    device='1,0',       # check via `arecord -l`; format is '<card_nr>,<device_nr>'.
    format='S16_LE',    # format (16 bit, little endian) - depending on the connected microphone.
    channels=2,         # number of channels (1: mono, 2: stereo) - depending on the connected microphone.
)

ui = Namespace(
    bot_token='',         # The Telegram bot token.
    chat_id=0,            # The chat id to communicate with.
    maximum_playback=60,  # [seconds] the number of seconds of most recent audio that is stored and can be retrieved via the UI.
    notify_playback=6,    # [seconds] when the `audio.threshold` is crossed a notification is sent containing this duration of most recent audio recording.
    threshold=50_000,     # [a.u.] amplitude that triggers a notification - determine the right value heuristically - can be adjusted via the UI.
)
