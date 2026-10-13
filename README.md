# Yugiri Village · 유우기리 마을 (夕霧村)

밤의 골목에서 언덕 위 신사로 향하는 Unity 3D 탐험 게임입니다. 프로젝트 소스, 모델·텍스처·사운드, Blender 원본과 에셋 제작 스크립트를 함께 보관합니다.

![유우기리 마을의 골목](Screenshots/shot2_mid_alley_machiya.png)

## 실행

1. **Unity 6000.3.19f1**을 설치합니다.
2. Unity Hub에서 저장소 안의 `YugiriVillage` 폴더를 프로젝트로 추가합니다.
3. `Assets/Scenes/YugiriVillage.unity` 씬을 열고 **Play**를 누릅니다.

## 조작

| 조작 | 기능 |
|---|---|
| WASD | 이동 |
| 마우스 | 시점 회전 |
| 왼쪽 Shift | 달리기 |
| 마우스 오른쪽 버튼 | 확대 관찰 |
| F | 손전등 켜기·끄기 |
| E | 조사·상호작용 |
| Esc | 마우스 잠금 전환 |

## 구성

- `YugiriVillage/Assets`: 씬, 게임 코드, 셰이더, 모델, 재질, 텍스처, 사운드와 Unity 메타데이터
- `YugiriVillage/Packages`, `YugiriVillage/ProjectSettings`: 패키지 의존성과 프로젝트 설정
- `YugiriVillage/YugiriVillage_MasterAssets.blend`: Blender 제작 원본
- `tools`: 모델·PBR 텍스처·사운드 제작 스크립트와 로컬 제작 도구 연결 스크립트
- `Screenshots`: 플레이 장면과 에셋 미리보기

Unity의 `Library`, `Temp`, `Logs`, `UserSettings` 폴더는 프로젝트를 열 때 생성됩니다. 업로드 과정에서는 Unity 실행이나 게임 빌드를 수행하지 않았습니다.
