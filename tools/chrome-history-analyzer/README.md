# Chrome 사용기록 분석기 (로컬 전용 GUI)

이 PC에 저장된 Chrome(또는 Edge/Chromium 계열)의 방문 기록(History)을 읽어
도메인별 방문 통계, 시간대별 방문 분포, 검색어 사용 현황을 분석하는 데스크톱 GUI 프로그램입니다.

**모든 분석은 로컬 PC에서만 수행되며, 어떤 데이터도 외부로 전송하지 않습니다.**

## 요구 사항

- Python 3.8 이상
- tkinter (Windows/macOS 공식 Python 설치본에는 기본 포함)
  - Linux(Ubuntu/Debian)에서 없다면: `sudo apt install python3-tk`
- 추가 pip 설치 불필요 (표준 라이브러리만 사용)

## 실행 방법

```bash
python3 chrome_history_analyzer.py
```

Windows는 파일 탐색기에서 더블클릭하거나, 명령 프롬프트에서 `python chrome_history_analyzer.py`.

## 사용 방법

1. 프로그램을 열면 PC에 설치된 Chrome/Edge 프로필을 자동으로 감지해 상단 드롭다운에 표시합니다.
   - 자동 감지가 안 되면 **"파일 직접 선택..."** 버튼으로 History 파일을 직접 지정하세요.
   - 기본 경로 예시
     - Windows: `%LOCALAPPDATA%\Google\Chrome\User Data\Default\History`
     - macOS: `~/Library/Application Support/Google/Chrome/Default/History`
     - Linux: `~/.config/google-chrome/Default/History`
2. **분석 기간**(전체/7일/30일/90일/1년)을 선택합니다.
3. **분석 시작**을 누르면 아래 4개 탭에 결과가 표시됩니다.
   - **요약** — 총 방문 횟수, 고유 도메인 수, 가장 많이 방문한 도메인 Top 10, 시간대별(0~23시) 방문 분포
   - **도메인별 통계** — 도메인별 방문 횟수·비율·최초/최근 방문일 (CSV 내보내기 가능)
   - **방문 기록 상세** — 개별 방문 목록, 제목/URL 검색 필터, 선택 항목을 브라우저로 열기, CSV 내보내기
   - **검색어 분석** — Google/Naver/Bing 등에서 사용한 검색어와 빈도 (CSV 내보내기)

Chrome이 실행 중이라 History 파일이 잠겨 있어도 읽기 전용으로 열어 분석하므로 Chrome을 종료할 필요가 없습니다.

## 테스트용 샘플 데이터로 먼저 체험해보기

실제 Chrome 데이터 없이 동작을 확인하고 싶다면:

```bash
python3 make_sample_history.py   # 같은 폴더에 History_sample 파일 생성 (가상 데이터)
python3 chrome_history_analyzer.py
```

프로그램에서 **"파일 직접 선택..."** → 방금 생성된 `History_sample` 파일을 선택 → **분석 시작**.

`make_sample_history.py`가 만드는 데이터는 실제 방문 기록이 아닌 검증용 가상 데이터입니다.

## 참고

- 방문 시각은 Chrome이 UTC 기준으로 저장한 값을 이 PC의 로컬 시간대로 변환해 표시합니다.
- 검색어는 Chrome의 `keyword_search_terms` 테이블(기본 검색엔진으로 설정된 경우 가장 정확)을 우선 사용하고,
  없는 경우 방문 URL의 검색 파라미터(q=, query= 등)를 휴리스틱으로 추출합니다. 완벽하지 않을 수 있습니다.
- 방문 기록 상세 탭은 성능을 위해 최신 5,000건까지만 화면에 표시하며, CSV 내보내기는 필터링된 전체 데이터를 포함합니다.
