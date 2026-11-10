# SOP-01 환경 설치

- **언제:** 새 PC에서 처음 시작할 때, 또는 받아쓰기·조립이 갑자기 죽을 때
- **요청 예시:** "이 스킬 설치해 줘", "필요한 도구 설치해 줘"
- **결과:** 스킬 설치, Python·ffmpeg·Whisper 준비, `doctor.py`의 필수 항목이 모두 OK

## 1. 편집 스킬 설치

1. 스킬 zip(`smartdaddy-video-edit.zip`)을 빈 폴더에 풀고 `SKILL.md`와 `scripts/`를 먼저 읽어 본다.
2. `smartdaddy-video-edit/` 폴더를 `~/.claude/skills/`에 복사한다.
3. 같은 이름의 폴더가 이미 있으면, 기존 `references/rules.md`의 `## 내 규칙` 아래 내용을 새 파일로 옮긴다. 기존 폴더는 `smartdaddy-video-edit_backup_<날짜>`로 남긴다.
4. 스킬이 바로 잡히지 않으면 새 대화(세션)를 연다.

## 2. Python 3.12 (관리자 권한 없이)

```powershell
winget install --id Python.Python.3.12 -e --silent --scope user --accept-package-agreements --accept-source-agreements --override "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_test=0"
```

설치 위치는 `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`다. 이미 켜져 있던 앱은 PATH 변경을 모르므로 전체 경로로 부르거나 앱을 다시 켠다.

## 3. 패키지·크로미움·ffmpeg

```powershell
python "$HOME\.claude\skills\smartdaddy-video-edit\scripts\doctor.py" --fix
```

이 명령은 `requirements.txt` 설치, `playwright install chromium`, `winget install Gyan.FFmpeg`를 한 번에 처리한다.

## 4. 이 PC 전용: 패키지 버전 고정

이 PC의 `C:\Windows\System32\msvcp140.dll`은 14.31로 오래된 버전이다. 최신 빌드 패키지는 불러오는 순간 `Windows fatal exception: access violation`으로 죽는다.

| 증상 | 원인 패키지 | 고정 버전 |
|---|---|---|
| Whisper 모델 불러올 때 죽음 | ctranslate2 4.8.5 | `ctranslate2==4.6.0` + `setuptools<80` |
| 음성 구간 감지(VAD)에서 죽음 | onnxruntime 1.31.1 | `onnxruntime==1.18.1` |
| `open() got an unexpected keyword argument 'metadata_errors'` | av 19 | `av<15` (14.2.0) |
| onnxruntime 1.18이 numpy를 1.26으로 내림 → opencv 충돌 | opencv-python 5.0 | `opencv-python<4.11` |

```powershell
python -m pip install "ctranslate2==4.6.0" "setuptools<80"
python -m pip install --only-binary :all: "av>=11,<15" "onnxruntime==1.18.1" "opencv-python<4.11"
python -m pip check
```

Microsoft Visual C++ 재배포 패키지를 최신으로 설치하면(관리자 권한 필요) 이 제한이 풀린다.

## 5. 확인

```powershell
python "$HOME\.claude\skills\smartdaddy-video-edit\scripts\doctor.py"
```

`필수 항목 모두 준비됨`이 나오면 끝이다. NVIDIA GPU가 없다는 주의는 정상이다. 받아쓰기가 CPU로 돌아갈 뿐이다.
