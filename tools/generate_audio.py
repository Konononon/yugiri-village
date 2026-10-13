import wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, lfilter

AUDIO_DIR = Path(r"c:\Users\gksix\Downloads\새 폴더 (2)\YugiriVillage\Assets\Audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
SR = 44100


def save_wav(filename: str, data: np.ndarray):
    data = np.clip(data, -1.0, 1.0)
    pcm = (data * 32767.0).astype(np.int16)
    with wave.open(str(AUDIO_DIR / filename), "wb") as wf:
        wf.setnchannels(1 if pcm.ndim == 1 else pcm.shape[1])
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def bandpass(sig, low, high):
    b, a = butter(2, [low / (SR * 0.5), high / (SR * 0.5)], btype="band")
    return lfilter(b, a, sig)


def lowpass(sig, cutoff):
    b, a = butter(2, cutoff / (SR * 0.5), btype="low")
    return lfilter(b, a, sig)


def gen_night_rain_wind():
    dur = 12.0
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    rng = np.random.default_rng(10)

    # Rain patter (filtered pink/white noise + micro droplets)
    white = rng.standard_normal(n)
    rain_body = bandpass(white, 700, 6500) * 0.14

    # Eerie mountain wind (slowly modulated low-band noise)
    wind_noise = bandpass(rng.standard_normal(n), 90, 480)
    wind_mod = 0.5 + 0.5 * np.sin(2 * np.pi * t / 6.0) * np.sin(2 * np.pi * t / 4.0)
    wind = wind_noise * wind_mod * 0.25

    # Ominous Japanese horror drone (55Hz + 82.4Hz + 116.5Hz tritone shimmer)
    drone = (
        0.08 * np.sin(2 * np.pi * 55.0 * t)
        + 0.05 * np.sin(2 * np.pi * 82.41 * t + 0.4 * np.sin(2 * np.pi * 0.25 * t))
        + 0.04 * np.sin(2 * np.pi * 116.54 * t)
    )

    sig = rain_body + wind + drone
    # Crossfade loop ends (first/last 0.5s)
    fade = int(SR * 0.5)
    w = np.linspace(0, 1, fade)
    sig[:fade] = sig[:fade] * w + sig[-fade:] * (1.0 - w)
    save_wav("Ambience_NightRainWind.wav", sig)


def gen_fluorescent_hum():
    dur = 4.0
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    rng = np.random.default_rng(20)
    hum = (
        0.18 * np.sin(2 * np.pi * 60.0 * t)
        + 0.24 * np.sin(2 * np.pi * 120.0 * t)
        + 0.11 * np.sin(2 * np.pi * 240.0 * t)
        + 0.06 * np.sin(2 * np.pi * 360.0 * t)
        + bandpass(rng.standard_normal(n), 1200, 4800) * 0.03 * (0.6 + 0.4 * np.sin(2 * np.pi * 3.0 * t))
    )
    save_wav("Hum_FluorescentVending.wav", hum)


def gen_footsteps():
    rng = np.random.default_rng(30)
    # 4 wet asphalt footsteps
    for i in range(1, 5):
        dur = 0.36
        n = int(SR * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        thud = np.sin(2 * np.pi * (110 - 65 * (t / dur)) * t) * np.exp(-t * 28.0) * 0.55
        grit = bandpass(rng.standard_normal(n), 500, 3200) * np.exp(-t * 18.0) * 0.45
        splash = bandpass(rng.standard_normal(n), 2200, 8500) * np.exp(-np.abs(t - 0.045) * 22.0) * 0.42
        save_wav(f"Footstep_WetAsphalt_{i}.wav", thud + grit + splash)

    # 2 stone step footsteps
    for i in range(1, 3):
        dur = 0.30
        n = int(SR * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        clack = np.sin(2 * np.pi * (160 - 80 * (t / dur)) * t) * np.exp(-t * 34.0) * 0.65
        scrape = bandpass(rng.standard_normal(n), 900, 4800) * np.exp(-t * 24.0) * 0.40
        save_wav(f"Footstep_Stone_{i}.wav", clack + scrape)


def gen_sfx():
    rng = np.random.default_rng(40)
    # Flashlight click
    dur = 0.12
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    click = bandpass(rng.standard_normal(n), 1500, 7000) * (
        np.exp(-t * 95.0) + 0.7 * np.exp(-np.maximum(0, t - 0.035) * 110.0) * (t >= 0.035)
    )
    save_wav("SFX_FlashlightClick.wav", click * 0.85)

    # Shrine Suzu Bell
    dur = 3.2
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    env = np.exp(-t * 1.8) * (1.0 - np.exp(-t * 60.0))
    bell = (
        0.40 * np.sin(2 * np.pi * 1180.0 * t)
        + 0.28 * np.sin(2 * np.pi * 1765.0 * t)
        + 0.20 * np.sin(2 * np.pi * 2490.0 * t)
        + 0.12 * np.sin(2 * np.pi * 3820.0 * t)
    ) * env
    save_wav("SFX_ShrineSuzuBell.wav", bell * 0.75)

    # Horror Stinger
    dur = 3.5
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    sub = np.sin(2 * np.pi * (68.0 - 12.0 * (t / dur)) * t) * np.exp(-t * 0.9) * 0.6
    shriek = (
        np.sin(2 * np.pi * 466.16 * t + 3.0 * np.sin(2 * np.pi * 7.5 * t))
        + np.sin(2 * np.pi * 493.88 * t)
    ) * np.exp(-t * 1.1) * 0.25
    breath = bandpass(rng.standard_normal(n), 400, 2600) * np.exp(-t * 1.3) * 0.25
    save_wav("SFX_HorrorStinger.wav", sub + shriek + breath)


def main():
    print("Generating custom procedural horror audio clips...")
    gen_night_rain_wind()
    gen_fluorescent_hum()
    gen_footsteps()
    gen_sfx()
    print(f"All audio clips saved to {AUDIO_DIR}")


if __name__ == "__main__":
    main()
