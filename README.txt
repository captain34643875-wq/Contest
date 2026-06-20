Disaster Commander
재난 대응 전략 시뮬레이션 게임

제작자:

=== 실행 방법 ===
1. Python 3.12 이상을 설치합니다.
2. 터미널(명령 프롬프트)에서 프로젝트 폴더로 이동한 후 다음 명령어를 실행합니다:
   pip install -r requirements.txt
3. main.py 파일을 실행합니다:
   python main.py

=== 리소스 구성 ===
bgm 폴더 안에 아래 3개의 파일이 있어야 BGM이 정상 재생됩니다.
- bgm/default_bgm.mp3
- bgm/disaster_bgm.mp3
- bgm/result_bgm.mp3

=== 조작법 ===
- 1 ~ 7 숫자키 : 명령 즉시 발동 (대피령, 구조대, 소방대 등)
- TAB          : 집중 재난 포커스 전환
- E            : 대피 모드 (시민 직접 이동)
- B            : 상점 열기/닫기
- P 또는 ESC   : 게임 일시정지
- H            : UI 숨김 / 보이기
- 마우스 오른쪽 버튼 드래그 : 맵 이동

=== 제출용 메모 ===
- pygame만 사용하는 단일 파일 프로젝트입니다.
- BGM은 bgm 폴더를 기준으로 상대경로로 불러옵니다.
- bgm 폴더가 없거나 파일이 없으면 음악 없이 실행됩니다.
- requirements.txt에 명시된 pygame 설치 후 실행해주세요.

문제가 발생하면 pygame 설치 상태를 확인해 주세요.
