# GitHub를 처음 쓰는 연구자를 위한 안내

## 1. GitHub는 무엇인가요?

GitHub는 파일과 그 수정 이력을 함께 보관하는 인터넷 서비스입니다. 저장소(repository)는 인터넷 폴더, README는 그 폴더의 첫 안내문, commit은 변경 내용을 저장한 기록, release는 이름표를 붙인 배포 판본이라고 이해하면 됩니다.

심사자에게 필요한 것은 “자료가 있다”는 설명보다, 자료를 받을 주소와 같은 결과를 얻는 실행 방법입니다. 이 저장소는 그 주소를 마련하는 곳입니다.

## 2. 우리 저장소를 여세요

아래 주소를 엽니다. 열람·내려받기에는 로그인이 필요하지 않습니다.

https://github.com/chaeyoungjoo-eng/yeongjo-min-reproducibility

저장소 이름 옆의 **Public**은 누구나 열람할 수 있다는 뜻입니다. 자료 수정은 저장소 권한이 있는 계정에서만 할 수 있습니다. 열람 권한과 편집 권한은 다릅니다.

## 3. 파일이 들어갔는지 살펴보세요

첫 화면의 **Code** 탭은 폴더 안을 보여 줍니다. README 아래 설명은 첫 안내문입니다. `docs`를 누르면 설명서가 보입니다. 데이터가 들어 있는 전체 묶음은 **Releases**의 `yeongjo-min-dev103c1-repro-v1.zip`을 내려받으면 됩니다. 뒤로 가려면 저장소 이름을 누르면 됩니다. `.gz`는 용량을 줄인 파일입니다. 코드가 직접 읽으므로 따로 풀지 않아도 됩니다.

## 4. 새 파일을 올리는 기본 방법

1. 파일을 넣을 폴더를 엽니다.
2. **Add file → Upload files**를 누릅니다.
3. 올릴 파일을 선택하거나 화면에 끌어 놓습니다.
4. 파일 이름을 확인합니다.
5. 저장 설명란에 무엇을 올렸는지 씁니다. 예: `dev103c1 재현 데이터 추가`.
6. **Commit changes**를 눌러 저장합니다.
7. 저장소 화면에 파일이 보이는지 확인합니다.

브라우저 업로드는 파일 하나가 25 MiB 이하여야 합니다. 이 묶음은 그 제한 안에서 파일을 나눴습니다. 큰 자료가 생기면 일반 폴더에 무리하게 넣기보다 Releases의 첨부 파일을 사용하는 방식을 검토합니다. GitHub 공식 안내: https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github

### 데이터 전체 묶음은 Releases에 올리기

우리 묶음은 약 41 MB이므로 일반 파일 업로드의 25 MiB 제한을 넘습니다. **Releases → Create a new release**에서 판본 이름을 입력하고 첨부 영역에 ZIP을 넣습니다. 첨부 파일 하나는 2 GiB 미만이어야 합니다. 올린 뒤에는 ZIP 이름이 화면에 보이는지 확인합니다. 데이터·코드·설명을 한 ZIP에 넣어 독자가 한 번에 받도록 합니다.

## 5. 같은 이름의 파일을 고칠 때

먼저 수정할 파일이 맞는지 확인합니다. 데이터를 고친 뒤에는 기대 결과와 검증 기록도 함께 갱신해야 합니다. 원자료·확정 판정·배포 판본을 설명 없이 바꾸면 독자가 어느 자료를 사용했는지 알 수 없습니다. 확정 배포본은 새 판본 이름으로 구별합니다.

## 6. 논문에 사용할 판본을 고정하기

계산 검증과 공개 범위 확인을 마친 뒤 저장소의 **Releases → Create a new release**에서 판본 이름표를 붙입니다. 예: `dev103c1-repro-v1`. 논문에는 저장소 첫 주소에 더해 실제 사용한 release 또는 commit을 적어, 나중에 파일이 바뀌어도 당시 자료를 찾게 합니다. 비공개 저장소에 release를 만들어도 저장소가 자동으로 공개되지는 않습니다.

공식 안내: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

## 7. 심사자·독자에게 전달하기

현재는 공개 상태이므로 고정 배포판 주소를 가진 심사자·독자가 로그인 없이 자료를 받을 수 있습니다. 인용할 때에는 실제 사용한 판본명과 고정 커밋을 함께 밝힙니다.

전달할 내용은 세 가지입니다. ① 내려받을 판본 주소 ② `reproduce.py` 실행 방법 ③ 무엇을 재현하고 무엇은 아직 재현하지 못하는지에 대한 설명입니다.

## 8. 나중에 갖출 인용 정보

저자명, 자료 제목, 판본, 배포일, 주소, 이용허락을 확정합니다. `CITATION.cff`를 사용하면 GitHub에 인용 안내를 표시할 수 있습니다. DOI는 별도의 영구 보관 서비스와 연결해 발급받는 경로를 검토합니다. GitHub에 올린 것만으로 DOI가 생기지는 않습니다.

공식 안내: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files
