import os
import time

import psutil
import pyautogui
import pyperclip
import undetected_chromedriver as uc
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# =====================================================
# ⚙️ 사용자 설정 상수
# =====================================================
TARGET_MODEL_INDEX = 2

# "도구 더보기"를 눌러야만 나타나는 하위 메뉴 항목들을 정의합니다.
SUBMENU_TOOLS = [
    "Canvas",
    "Deep Research",
    "음악 만들기",
    "가이드 학습",
    "개인 인텔리전스",
]


def kill_chrome_processes():
    """충돌 방지를 위해 기존 크롬 프로세스를 종료"""
    for proc in psutil.process_iter(["name"]):
        try:
            if "chrome" in proc.info.get("name", "").lower():
                proc.kill()
        except Exception:
            pass

    time.sleep(1)


def wait_for_response(driver):
    """답변 생성을 대기하는 함수"""
    print("⏳ 답변 생성 대기 중... (타임아웃 없음)")
    time.sleep(2)

    stop_btn_xpath = (
        "//button[contains(@aria-label, '중지') or contains(@aria-label, 'Stop')]"
    )

    generating_started = False
    for _ in range(40):
        stop_btns = driver.find_elements(By.XPATH, stop_btn_xpath)
        if any(btn.is_displayed() for btn in stop_btns):
            generating_started = True
            print("▶️ 생성 중 상태 확인됨 ('응답 중지' 버튼 감지)")
            break
        time.sleep(0.5)

    if generating_started:
        while True:
            stop_btns = driver.find_elements(By.XPATH, stop_btn_xpath)
            if not any(btn.is_displayed() for btn in stop_btns):
                print("✅ 답변 생성 완료 ('응답 중지' 버튼 사라짐)!")
                time.sleep(2)
                break
            time.sleep(1)
    else:
        print("✅ 답변이 생성 완료되었습니다 ('응답 중지' 버튼 미감지).")
        time.sleep(2)


def process_queue(driver, task_queue):
    """정의된 큐(작업 리스트)를 순차적으로 실행하는 함수"""
    wait = WebDriverWait(driver, 20)

    for index, task in enumerate(task_queue):
        print(
            f"\n[{index + 1}/{len(task_queue)}] 📋 작업 시작: {task['prompt'][:20]}..."
        )

        try:
            # 1. 새 채팅 시작 여부
            if task.get("new_chat"):
                print("🔄 단축키(Ctrl + Shift + O)를 이용하여 새 채팅방을 생성합니다.")
                try:
                    actions = ActionChains(driver)
                    actions.key_down(Keys.CONTROL).key_down(Keys.SHIFT).send_keys(
                        "o"
                    ).key_up(Keys.SHIFT).key_up(Keys.CONTROL).perform()

                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div[contenteditable='true']")
                        )
                    )
                    time.sleep(2)
                    print("✅ 새 채팅방 전환 성공")
                except Exception as e:
                    print(f"⚠️ 새 채팅 단축키 조작 실패: {e}")

            # 2. 첨부 메뉴 액션 처리 (파일 업로드, 이미지 만들기, Canvas 등)
            action_name = task.get("attachment_action")
            if action_name:
                print(f"🚀 메뉴 확장 시도: {action_name}")
                try:
                    # ➕(첨부) 버튼 클릭
                    attach_btn_xpath = (
                        "//button[contains(@aria-label, '업로드') or "
                        "contains(@aria-label, '첨부') or "
                        "contains(@aria-label, 'Upload') or "
                        "contains(@aria-label, '파일')]"
                    )
                    wait.until(
                        EC.presence_of_element_located((By.XPATH, attach_btn_xpath))
                    )
                    attach_btns = driver.find_elements(By.XPATH, attach_btn_xpath)

                    for btn in attach_btns:
                        if btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            break
                    time.sleep(1)

                    # 서브 메뉴("도구 더보기") 탐색 및 클릭
                    if action_name in SUBMENU_TOOLS:
                        tools_xpath = "//*[contains(text(), '도구 더보기')]"
                        tools_item = wait.until(
                            EC.element_to_be_clickable((By.XPATH, tools_xpath))
                        )
                        driver.execute_script("arguments[0].click();", tools_item)
                        time.sleep(1)  # 서브 메뉴 렌더링 대기

                    # 목표 메뉴 아이템 클릭
                    menu_item_xpath = f"//*[contains(text(), '{action_name}')]"
                    menu_item = wait.until(
                        EC.element_to_be_clickable((By.XPATH, menu_item_xpath))
                    )
                    driver.execute_script("arguments[0].click();", menu_item)
                    print(f"✅ '{action_name}' 옵션 선택 완료")
                    time.sleep(1.5)

                    # '파일 업로드'인 경우 OS 열기 창 제어
                    if action_name == "파일 업로드" and task.get("file_path"):
                        file_path = os.path.abspath(task["file_path"])
                        if not os.path.exists(file_path):
                            print(f"⚠️ 에러: 업로드할 파일 없음. 경로: {file_path}")
                        else:
                            print("📂 윈도우 열기 창 대기 중...")
                            time.sleep(2)
                            pyperclip.copy(file_path)
                            pyautogui.hotkey("ctrl", "v")
                            time.sleep(0.5)
                            pyautogui.press("enter")
                            print("✅ 파일 업로드 완료, 대기 중...")
                            time.sleep(3)

                except Exception as e:
                    print(f"⚠️ 첨부 메뉴 조작 실패: {e}")

            # 3. 질문 입력 및 전송
            print("🚀 질문 입력 중...")
            input_box = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div[contenteditable='true']")
                )
            )

            input_box.click()
            time.sleep(0.5)
            input_box.send_keys(Keys.CONTROL + "a")
            input_box.send_keys(Keys.BACKSPACE)
            time.sleep(0.5)

            input_box.send_keys(task["prompt"])
            time.sleep(1.5)
            input_box.send_keys(Keys.ENTER)
            time.sleep(1)

            # 엔터가 동작하지 않았을 경우 수동 클릭
            if driver.execute_script(
                "return arguments[0].innerText.trim().length > 0;", input_box
            ):
                print("⚠️ 전송 버튼을 수동으로 클릭합니다.")
                try:
                    send_btn_xpath = (
                        "//button[contains(@aria-label, '메시지 보내기') or "
                        "contains(@aria-label, 'Send message')]"
                    )
                    wait.until(EC.element_to_be_clickable((By.XPATH, send_btn_xpath)))
                    send_btns = driver.find_elements(By.XPATH, send_btn_xpath)

                    clicked = False
                    for btn in send_btns:
                        if btn.is_displayed() and btn.is_enabled():
                            ActionChains(driver).move_to_element(btn).click(
                                btn
                            ).perform()
                            clicked = True
                            break

                    if not clicked:
                        print("❌ 활성화된 전송 버튼을 찾지 못했습니다.")
                except Exception as e:
                    print(f"❌ 수동 전송 버튼 클릭 중 에러: {e}")

            for _ in range(10):
                if driver.execute_script(
                    "return arguments[0].innerText.trim().length == 0;", input_box
                ):
                    print("✅ 질문 전송 확인 완료!")
                    break
                time.sleep(0.5)

            # 4. 답변 완료 대기
            wait_for_response(driver)

        except Exception as e:
            print(f"❌ 작업 [{index + 1}] 처리 중 에러 발생: {e}")


def start_gemini_manual_session():
    options = uc.ChromeOptions()
    current_dir = os.getcwd()
    profile_path = os.path.join(current_dir, "gemini_profile")

    if not os.path.exists(profile_path):
        os.makedirs(profile_path)

    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--start-maximized")
    options.add_argument("--no-first-run")
    options.add_argument("--no-service-autorun")
    options.add_argument("--password-store=basic")
    options.add_argument("--disable-blink-features=AutomationControlled")

    print("🚀 브라우저 실행중...")
    driver = uc.Chrome(options=options, version_main=148)
    driver.maximize_window()
    wait = WebDriverWait(driver, 20)

    try:
        driver.get("https://gemini.google.com/app")

        print("\n" + "=" * 50)
        print("📢 수동 로그인 필요")
        print("1. 구글 로그인 완료")
        print("2. Gemini 메인 화면 확인")
        print("3. 터미널에서 엔터")
        print("=" * 50)

        input("계속하려면 엔터...")
        time.sleep(5)
        print("현재 URL:", driver.current_url)

        try:
            print("🔍 모델 드롭다운 탐색 시작...")
            model_button_xpath = """
            //button[
                contains(., 'Flash')
                or contains(., 'Lite')
                or contains(., 'Pro')
            ]
            """
            wait.until(EC.presence_of_element_located((By.XPATH, model_button_xpath)))
            model_btns = driver.find_elements(By.XPATH, model_button_xpath)

            model_btn = next((btn for btn in model_btns if btn.is_displayed()), None)

            if model_btn:
                driver.execute_script("arguments[0].click();", model_btn)
                time.sleep(1)

                print(
                    f"⌨️ 키보드를 사용하여 {TARGET_MODEL_INDEX}번째 모델로 이동합니다..."
                )
                actions = ActionChains(driver)
                press_count = max(0, TARGET_MODEL_INDEX - 1)

                for _ in range(press_count):
                    actions.send_keys(Keys.ARROW_DOWN).pause(0.2)

                actions.send_keys(Keys.ENTER).perform()
                print(f"✅ {TARGET_MODEL_INDEX}번째 모델 선택 완료!")
                time.sleep(2)

            else:
                print("⚠️ 화면에 보이는 모델 버튼을 찾지 못했습니다.")

        except Exception as e:
            print(f"⚠️ 모델 선택 실패: {e}")

        # =====================================================
        # 큐(Queue) 작업 리스트 정의
        # =====================================================
        my_tasks = [
            {
                "prompt": "안녕, 내가 올린 파이썬 코드를 분석해주고, 시간 복잡도를 알려줘.",
                "attachment_action": "파일 업로드",
                "file_path": "test_code.py",
                "new_chat": True,
            },
            {
                "prompt": "이 주제에 대해서 심층 분석 보고서를 작성해줘.",
                "attachment_action": "Deep Research",
                "file_path": None,
                "new_chat": True,
            },
            {
                "prompt": "귀여운 강아지가 코딩하는 이미지를 그려줘.",
                "attachment_action": "이미지 만들기",
                "file_path": None,
                "new_chat": True,
            },
        ]

        print("\n🚀 지정된 큐(Queue) 자동 실행을 시작합니다...")
        process_queue(driver, my_tasks)
        print("\n🎉 모든 큐 작업이 성공적으로 완료되었습니다!")
        time.sleep(60)

    except Exception as e:
        print(f"❌ 전체 메인 로직 에러 발생: {e}")


if __name__ == "__main__":
    start_gemini_manual_session()
