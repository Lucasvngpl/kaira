import time
import random
from pylsl import StreamInfo, StreamOutlet

def create_64ch_dummy_lsl():
    # 1. Provide your exact 64-channel layout
    ch_names: list[str] = [
        "Fp1", "Fpz", "Fp2", "F7", "F3", "Fz", "F4", "F8",
        "FC5", "FC1", "FC2", "FC6", "M1", "T7", "C3", "Cz",
        "C4", "T8", "M2", "CP5", "CP1", "CP2", "CP6", "P7",
        "P3", "Pz", "P4", "P8", "POz", "O1", "O2", "EOG",
        "AF7", "AF3", "AF4", "AF8", "F5", "F1", "F2", "F6",
        "FC3", "FCz", "FC4", "C5", "C1", "C2", "C6", "CP3",
        "CP4", "P5", "P1", "P2", "P6", "PO5", "PO3", "PO4",
        "PO6", "FT7", "FT8", "TP7", "TP8", "PO7", "PO8", "Oz",
    ]
    
    # 2. Base Stream Setup (dynamically reading the list length)
    name = 'DummyEEG_64Ch'
    stream_type = 'EEG'
    channels = len(ch_names)  # Automatically sets to 64
    sample_rate = 100.0  
    data_type = 'float32'
    unique_id = 'dummy_64ch_eeg_98765'

    info = StreamInfo(name, stream_type, channels, sample_rate, data_type, unique_id)

    # 3. Inject the 64-channel pinout metadata
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
    
    try:
        while True:
            # Generate a random float value for all 64 channels
            sample = [random.uniform(-50.0, 50.0) for _ in range(channels)]
            outlet.push_sample(sample)
            time.sleep(1.0 / sample_rate)
    except KeyboardInterrupt:
        print("\n64-channel stream stopped.")

if __name__ == '__main__':
    create_64ch_dummy_lsl()
