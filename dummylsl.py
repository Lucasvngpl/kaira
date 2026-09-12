import time
import random
from pylsl import StreamInfo, StreamOutlet

def create_24ch_dummy_lsl():
    # 24 channel layout updated to match EE-511 layout. Works perfectly with the web app.
    ch_names: list[str] = [
        "Fp1", "Fp2", "F9", "F7", "F3", "Fz", "F4", "F8", "F10", 
    "T7", "C3", "Cz", "C4", "T8", "P7", "P3", "Pz", "P4", "P8", 
    "O1", "Oz", "O2", "CPz", "M1",
    ]
    
    # 2. Base Stream Setup (dynamically reading the list length)
    name = 'DummyEEG_24Ch'
    stream_type = 'EEG'
    channels = len(ch_names)  # Automatically sets to 24
    sample_rate = 512.0  # match the real EE-511 config so rehearsals are faithful
    data_type = 'float32'
    unique_id = 'dummy_24ch_eeg_98765'

    info = StreamInfo(name, stream_type, channels, sample_rate, data_type, unique_id)

    # 3. Inject the 24-channel pinout metadata
    desc = info.desc()
    chns = desc.append_child("channels")
    
    for label in ch_names:
        ch = chns.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "microvolts")
        
        # Explicitly tag EOG/Mastoids if your consumer software filters by type
        if label in ["EOG"]:
            ch.append_child_value("type", "EOG")
        elif label in ["M1", "M2"]:
            ch.append_child_value("type", "REF")
        else:
            ch.append_child_value("type", "EEG")

    # 4. Initialize the outlet
    outlet = StreamOutlet(info)

    print(f"Streaming '{name}' with {channels} channels initialized.")
    print("Press Ctrl+C to stop the stream.")
    
    # Chunked pushes: per-sample sleep can't keep pace at 512 Hz, and
    # +-25 uV keeps the noise inside physiological range so preprocess's
    # 150 uV artifact gate trusts it (uniform +-50 tripped the gate).
    chunk_size = 32
    try:
        while True:
            chunk = [
                [random.uniform(-25.0, 25.0) for _ in range(channels)]
                for _ in range(chunk_size)
            ]
            outlet.push_chunk(chunk)
            time.sleep(chunk_size / sample_rate)
    except KeyboardInterrupt:
        print("\n24-channel stream stopped.")

if __name__ == '__main__':
    create_24ch_dummy_lsl()
