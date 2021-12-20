import streamlit as st
import sys
import subprocess
import os
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
from pathlib import Path
import librosa
import soundfile
import plotly.graph_objs as go

################ Model ################
class Model:
    header = 'Combine Video'
    in1 = 'in1.mp4'
    in2 = 'in2.mp4'
    out = 'out.mp4'

    def __init__(self):
        if 'num' not in st.session_state:
            # initial values for widgets
            self.num = 0
            self.cliplen =  170
            self.delay1 = 0
            self.delay2 = 70
            self.swap = False
            
            # computed values
            self.snum = 0
            
    def __getattr__(self, key):
        return st.session_state[key]
    
    def __setattr__(self, key, value):
        st.session_state[key] = value

    def write_file(self, num, key):
        print(f"Upload {num}")
        if st.session_state[key] is None:
            return
        data = st.session_state[key].getvalue()
        print(f'WRITE FILE {st.session_state[key]}')

        with open(f'in{num}.mp4', "wb") as f:
            f.write(data)

    def combine(self):
        print("COMBINE!!!")
        start1 = get_start(Model.in1)
        start2 = get_start(Model.in2)
        combine_files(Model.in1, Model.in2, start1, start2, self.cliplen/1000, 
                      self.delay1/1000, self.delay2/1000, Model.out, self.swap)

################ View  ################
def view(m):
    st.set_page_config(
        page_title="Combine Video",
        page_icon="🎞️",
        layout="wide",
    )

    with st.sidebar:
        st.header(m.header)
        st.file_uploader('First Clip', type=['mp4'], on_change=m.write_file, key='upload1', args=[1, 'upload1'])
        st.file_uploader('Second Clip', type=['mp4'], on_change=m.write_file, key='upload2', args=[2, 'upload2'])
        st.number_input('Length of Clips (ms)', key='cliplen', step=5, min_value=100)
        st.number_input('Delay Before First Clip (ms)', key='delay1', step=5, min_value=0)
        st.number_input('Delay Before Second Clip (ms)', key='delay2', step=5, min_value=0)
        st.checkbox('Swap Audio', key='swap', help='Swap the audio for the video clips so that the audio for clip2 plays during the video for clip1 and vice-versa.')
        st.button('Combine!', on_click=m.combine)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(y=[''],x=[m.delay1],name='Delay1', marker_color='red', orientation='h'))
    fig.add_trace(go.Bar(y=[''],x=[m.cliplen],name='Clip1', marker_color='blue', orientation='h'))
    fig.add_trace(go.Bar(y=[''],x=[m.delay2],name='Delay2', marker_color='darkred', orientation='h'))
    fig.add_trace(go.Bar(y=[''],x=[m.cliplen],name='Clip2', marker_color='darkblue', orientation='h'))
    fig.update_layout(barmode='stack', title=f'Total Length: {m.delay1+m.delay2+2*m.cliplen} ms', xaxis_title='Time (ms)', height=300)
    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.video(m.upload1)
    c2.video(m.upload2)

    if os.path.exists(m.out):
        c3.video(m.out)
        c3.audio('out.wav')
        # with open('out.wav', "rb") as file:
        #     c3.download_button("Download WAV", file, mime='audio/wav')
    
################ Start  ################
view(Model())


def convert_mp4(vfile, srate, s1, s2):
    "create a wav file from an mp4.  s1 and s2 are ends of clips"
    p = Path(vfile)
    afile = p.with_suffix('.wav').as_posix()
    print(f"Writing \"{afile}\" as {srate} Hz wav file")
    try:
        p = subprocess.run(['ffmpeg', '-hide_banner', '-y',  '-i', vfile, '-ac', '1', '-acodec', 'pcm_f32le', '-ar', str(srate), afile], capture_output=True, text=True)
        if p.returncode:
            print(p.stderr)
    except FileNotFoundError:
        print("ERROR: Could not find ffmpeg.  Required for converting video files to wav files.")

    # Now we apply a 5ms ramp to the ends of the clips
    data, sr = librosa.load(afile, mono=False, sr=None)
    print(f'len(data)={len(data)} sr={sr}')
    # we need the position in the data 5ms before s1 and s2
    print(f's1={s1}  s2={s2}')

    s1 = int(sr * (s1 - .004))
    s2 = int(sr * (s2 - .004))
    print(f's1={s1}  s2={s2}')
    ramplen = int(sr * .005)
    print(f'ramplen={ramplen}')
    for i in range(ramplen):
        data[s1+i] *= (ramplen - i)/ramplen
        data[s2+i] *= (ramplen - i)/ramplen
    soundfile.write(afile, data, sr, 'FLOAT')

def combine_files(name1, name2, start1, start2, len, delay1, delay2, oname, swap):
    "combine two video clips with specified delays"
    print(f'COMBINE {name1} {name2} {start1} {start2} {len} {delay1} {delay2} {oname} {swap}')
    video1 = VideoFileClip(name1)
    print(f"Video 1 is {video1.size},  {video1.fps} fps, audio: {video1.audio.fps} Hz, {video1.duration} seconds")
    video2 = VideoFileClip(name2)
    print(f"Video 2 is {video2.size},  {video2.fps} fps, audio: {video2.audio.fps} Hz, {video2.duration} seconds")

    clip1 = video1.subclip(start1 - delay1, start1 + len)
    clip2 = video2.subclip(start2 - delay2, start2 + len)
    if swap:
        aclip1 = AudioFileClip(name1).subclip(start1 - delay2, start1 + len)
        aclip2 = AudioFileClip(name2).subclip(start2 - delay1, start2 + len)
        clip1.audio = CompositeAudioClip([aclip2])
        clip2.audio = CompositeAudioClip([aclip1])
    
    clips = [clip1, clip2]

    processed_video = concatenate_videoclips(clips)
    processed_video.write_videofile(
        oname,
        fps=video1.fps,
        preset='ultrafast',
        codec='libx264'
        )
    video1.close()
    video2.close()
    convert_mp4(oname, 32000, delay1+len, delay1+delay2+2*len)

def get_start(fname):
    "returns the time in seconds for the first sound in the file"
    cmdlist = ["ffmpeg",  "-hide_banner",  "-y",  "-vn", "-i",  fname, "-af",  "silencedetect=n=-20dB:d=0.1", "foo.mp4"]
    p = subprocess.run(cmdlist, capture_output=True, text=True)
    out = p.stderr.split('\n')
    count = sum('silence_start' in line for line in out)
    if count != 2:
        print(f"ERROR: expected silence before and after clip. Found {count} silences.")
        sys.exit(1)

    count = 0
    for line in out:
        if 'silence_end' in line:
            speech_start = float(line.split('|')[0].split()[-1])
            break
    print(f'{fname}: speech_start={speech_start}')
    os.remove("foo.mp4")
    return speech_start
