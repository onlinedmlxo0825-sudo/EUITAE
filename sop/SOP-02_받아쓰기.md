# SOP-02 녹화본 받아쓰기·장면 미리보기

- **언제:** 새 녹화본으로 편집을 시작할 때
- **요청 예시:** "D:\녹화본 받아쓰기 돌려 줘"
- **결과:** `<프로젝트>/01_asr/<클립>/` 아래 `words.json`, `transcript.txt`, `audio16k.wav`, 그리고 `<프로젝트>/00_sheets/<클립>.jpg`

## 1. 프로젝트 폴더 만들기

`클로드 영상편집/<MMDD>_<내용>_브이로그/`를 만들고 그 아래에 `00_sheets`, `01_asr`, `02_plan`, `03_capcut`, `04_preview`를 둔다. 원본 영상은 원래 자리에 그대로 둔다.

## 2. 클립 목록 확인

ffprobe로 길이, 해상도, 회전, 촬영 시각을 본다. 고프로의 `creation_time`은 실제 순서와 어긋날 수 있으니, 순서는 장면 내용으로 다시 맞춘다.

## 3. 받아쓰기 (CPU 기준 약 69분 분량에 20분 안팎)

```powershell
python -I scripts\asr_all.py "$HOME\.claude\skills\smartdaddy-video-edit\scripts" "D:\녹화본" ".\<프로젝트>\01_asr" large-v3-turbo
```

- 모델은 처음 한 번 내려받는다(large-v3-turbo 약 1.5GB).
- 중간에 멈춰도 다시 돌리면 `words.json`이 있는 클립은 건너뛴다.
- `asr_all.py`는 하위 폴더 이름에 `편집`이 들어간 경로와 `GH010064`(11/3 촬영 6초 클립)를 뺀다. 다른 프로젝트에서는 이 줄을 확인한다.
- 바로 죽으면 [SOP-01의 4번](SOP-01_환경설치.md)을 보고 `scripts\asr_probe.py`로 단계를 나눠 확인한다.

## 4. 장면 미리보기(클립당 5x4 썸네일, 키프레임만 읽어서 빠름)

```powershell
ffmpeg -skip_frame nokey -i <클립> -vf "select='isnan(prev_selected_t)+gte(t-prev_selected_t\,<길이/20>)',scale=256:144:force_original_aspect_ratio=decrease,pad=256:144:(ow-iw)/2:(oh-ih)/2,drawtext=fontfile='C\:/Windows/Fonts/arial.ttf':text='%{pts\:hms}':x=4:y=4:fontsize=14:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=5x4" -fps_mode vfr -frames:v 1 <프로젝트>\00_sheets\<클립>.jpg
```

`drawtext`에는 `fontfile`을 꼭 지정한다. 지정하지 않으면 Fontconfig 오류로 이미지가 만들어지지 않는다.

## 5. 컷 위치 잡기

받아쓰기 문장 하나가 수십 초로 길게 묶인 곳은 단어 시각으로 확인한다.

```powershell
python -I scripts\words_in.py ".\<프로젝트>\01_asr" GH010066:150-180 20261108_201816:0-31
```
