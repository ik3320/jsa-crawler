import requests
import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 본인의 웹앱 URL로 교체하세요
GAS_URL = "https://script.google.com/macros/s/AKfycbyRFG-aEn67ooqn84calnJlttxhFRGu1J5TtmT2Rka5fVAiONJFJHkoMHk4offjTTK5/exec"

def get_member_list():
    """시트에서 명단을 가져오고, 주소가 없는 멤버는 여기서 1차로 걸러냅니다."""
    try:
        response = requests.get(f"{GAS_URL}?action=getMemberList")
        # 응답이 정상인지 확인 (200 OK)
        if response.status_code != 200:
            print(f"GAS 연결 실패: 상태코드 {response.status_code}")
            return []
            
        raw_data = response.json()
        
        # [로직 추가] ELO 주소가 제대로 입력된 멤버만 필터링
        valid_members = [
            m for m in raw_data 
            if m.get('eloUrl') and "http" in m['eloUrl']
        ]
        
        print(f"전체 {len(raw_data)}명 중 ELO 주소가 등록된 {len(valid_members)}명을 확인했습니다.")
        return valid_members
        
    except Exception as e:
        print(f"명단 가져오기 실패: {e}")
        print("팁: GAS 배포 후 '새 배포'를 했는지, 액세스 권한이 '모든 사용자'인지 확인하세요.")
        return []

def scrape_elo_board(driver, url, sId):
    """ELO 보드 크롤링 (기존 로직 유지)"""
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.list-board")))

        current_month = datetime.now().strftime("%Y-%m")
        rows = driver.find_elements(By.CSS_SELECTOR, "div.list-board table tbody tr")
        
        monthly_total = 0
        monthly_wins = 0

        for row in rows:
            tds = row.find_elements(By.TAG_NAME, "td")
            if not tds or len(tds) < 1: continue
            
            first_td = tds[0]
            date_text = first_td.text.strip()
            bg_color = first_td.value_of_css_property("background-color")

            if date_text.startswith(current_month):
                monthly_total += 1
                if "0, 204, 255" in bg_color: # 승리 색상
                    monthly_wins += 1

        win_rate = f"{(monthly_wins / monthly_total * 100):.1f}%" if monthly_total > 0 else "0.0%"
        print(f"[성공] {sId}: {monthly_total}전 {monthly_wins}승 ({win_rate})")
        
        return {"sId": sId, "eloCount": monthly_total, "eloRate": win_rate}
    except Exception as e:
        print(f"[건너뜀] {sId}: 데이터 로딩 실패 또는 테이블 없음")
        return None

def main():
    members = get_member_list()
    if not members:
        print("작업을 중단합니다. 시트의 W열(ELO주소)을 확인해 주세요.")
        return

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # 아래 옵션은 차단 방지를 위해 추가
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    final_results = []
    for member in members:
        res = scrape_elo_board(driver, member['eloUrl'], member['sId'])
        if res:
            final_results.append(res)
        time.sleep(1.5) # 과부하 방지

    driver.quit()

    if final_results:
        payload = {"action": "updateBulkElo", "payload": final_results}
        res = requests.post(GAS_URL, data=json.dumps(payload))
        print(f"\n시트 전송 결과: {res.text}")
    else:
        print("업데이트할 전적 데이터가 없습니다.")

if __name__ == "__main__":
    main()