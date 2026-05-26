import os
import time

import psutil
import pyautogui  # 윈도우 창 제어를 위한 추가 라이브러리
import pyperclip  # 클립보드 제어를 위한 추가 라이브러리 (한영키 오류 방지)
import undetected_chromedriver as uc
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# =====================================================
# ⚙️ 사용자 설정 상수 (코드 맨 위에서 관리)
# =====================================================
# 드롭다운 메뉴에서 몇 번째 모델을 선택할지 지정합니다.
# 1: 첫 번째 모델
# 2: 두 번째 모델
# 3: 세 번째 모델
# * 제미나이의 메뉴 개수와 순서는 구글 업데이트에 따라 다를 수 있습니다.
TARGET_MODEL_INDEX = 2


def kill_chrome_processes():
    """충돌 방지를 위해 기존 크롬 프로세스를 종료"""
    for proc in psutil.process_iter(["name"]):
        try:
            if "chrome" in proc.info["name"].lower():
                proc.kill()
        except:
            pass

    time.sleep(1)


def wait_for_response(driver):
    """
    답변 생성을 대기하는 함수.
    """
    print("⏳ 답변 생성 대기 중... (타임아웃 없음)")

    # 엔터 누른 직후 파일 분석 및 서버 로딩 시간을 약간 줍니다.
    time.sleep(2)

    # '응답 생성 중지' 등 텍스트가 바뀔 것을 대비해 '중지'로 넓게 잡습니다.
    stop_btn_xpath = (
        "//button[contains(@aria-label, '중지') or contains(@aria-label, 'Stop')]"
    )

    # 1단계: '응답 중지' 버튼이 뜨는지 확인 (최대 20초 대기)
    generating_started = False
    for _ in range(40):
        stop_btns = driver.find_elements(By.XPATH, stop_btn_xpath)
        # 여러 개가 잡히더라도 화면에 실제로 보이는 버튼이 있는지 확인
        if any(btn.is_displayed() for btn in stop_btns):
            generating_started = True
            print("▶️ 생성 중 상태 확인됨 ('응답 중지' 버튼 감지)")
            break
        time.sleep(0.5)

    # 2단계: 대기 로직 처리
    if generating_started:
        # 생성이 시작되었다면, 버튼이 사라질 때까지 무한정 기다립니다.
        while True:
            stop_btns = driver.find_elements(By.XPATH, stop_btn_xpath)
            # 모든 버튼이 더 이상 화면에 없으면 생성 완료로 간주
            if not any(btn.is_displayed() for btn in stop_btns):
                print("✅ 답변 생성 완료 ('응답 중지' 버튼 사라짐)!")
                time.sleep(2)  # 안정화를 위한 짧은 대기
                break
            time.sleep(1)
    else:
        # 20초가 지났는데도 버튼이 안 떴다면, 짧은 단답형이 20초 안에 끝난 경우입니다.
        print("✅ 답변이 생성 완료되었습니다 ('응답 중지' 버튼 미감지).")
        time.sleep(2)


def process_queue(driver, task_queue):
    """
    정의된 큐(작업 리스트)를 순차적으로 실행하는 함수.
    """
    wait = WebDriverWait(driver, 20)

    for index, task in enumerate(task_queue):
        print(
            f"\n[{index + 1}/{len(task_queue)}] 📋 작업 시작: {task['prompt'][:20]}..."
        )

        try:
            # --------------------------------------------------
            # 1. 새 채팅 시작 여부 (사이드바 로직 제거, 단축키 사용)
            # --------------------------------------------------
            if task.get("new_chat"):
                print("🔄 단축키(Ctrl + Shift + O)를 이용하여 새 채팅방을 생성합니다.")
                try:
                    actions = ActionChains(driver)
                    actions.key_down(Keys.CONTROL).key_down(Keys.SHIFT).send_keys(
                        "o"
                    ).key_up(Keys.SHIFT).key_up(Keys.CONTROL).perform()

                    # 채팅방 환경이 완전히 초기화될 때까지 대기 (입력창 활성화 확인)
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div[contenteditable='true']")
                        )
                    )
                    time.sleep(2)
                    print("✅ 새 채팅방 전환 성공")
                except Exception as e:
                    print(f"⚠️ 새 채팅 단축키 조작 실패: {e}")

            # --------------------------------------------------
            # 2. 파일 업로드 (PyAutoGUI 우회 방식 적용)
            # --------------------------------------------------
            if task.get("file_path"):
                file_path = os.path.abspath(task["file_path"])

                if not os.path.exists(file_path):
                    print(
                        f"⚠️ 에러: 업로드할 파일이 존재하지 않습니다. 경로: {file_path}"
                    )
                else:
                    print(f"🚀 파일 업로드 시도: {file_path}")
                    try:
                        # ➕(첨부) 버튼 클릭
                        attach_btn_xpath = "//button[contains(@aria-label, '업로드') or contains(@aria-label, '첨부') or contains(@aria-label, 'Upload') or contains(@aria-label, '파일')]"

                        # 첨부 버튼도 여러 개 뜰 수 있으므로 화면에 보이는 것 탐색
                        wait.until(
                            EC.presence_of_element_located((By.XPATH, attach_btn_xpath))
                        )
                        attach_btns = driver.find_elements(By.XPATH, attach_btn_xpath)

                        for btn in attach_btns:
                            if btn.is_displayed():
                                driver.execute_script("arguments[0].click();", btn)
                                break
                        time.sleep(1)  # 메뉴 렌더링 대기

                        # '파일 업로드' 메뉴 클릭 (OS 열기 창 강제 호출)
                        menu_item_xpath = "//*[contains(text(), '파일 업로드')]"
                        menu_item = wait.until(
                            EC.element_to_be_clickable((By.XPATH, menu_item_xpath))
                        )
                        driver.execute_script("arguments[0].click();", menu_item)

                        print("📂 윈도우 열기 창 대기 중...")
                        time.sleep(2)  # 열기 창이 완전히 뜰 때까지 대기

                        # PyAutoGUI를 사용해 파일 경로 입력 후 엔터
                        # 한/영 키 상태에 따른 오타를 방지하기 위해 클립보드(pyperclip) 활용
                        pyperclip.copy(file_path)
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.5)
                        pyautogui.press('enter')

                        print("✅ GUI 제어로 파일 업로드 완료, 칩(Chip) 생성 대기 중...")
                        time.sleep(3)

                    except Exception as e:
                        print(f"⚠️ 파일 업로드 실패: {e}")

            # --------------------------------------------------
            # 3. 질문 입력 및 전송 (개선된 버전)
            # --------------------------------------------------
            print("🚀 질문 입력 중...")

            input_box = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div[contenteditable='true']")
                )
            )

            # 기존 텍스트 지우기
            input_box.click()
            time.sleep(0.5)  # 클릭 후 포커스 활성화 대기
            input_box.send_keys(Keys.CONTROL + "a")
            input_box.send_keys(Keys.BACKSPACE)
            time.sleep(0.5)

            # 텍스트 입력
            input_box.send_keys(task["prompt"])

            # ⭐️ 핵심: 프론트엔드가 텍스트 입력을 감지하고 전송 버튼을 활성화할 시간을 줍니다.
            time.sleep(1.5)

            # 엔터 입력 시도
            input_box.send_keys(Keys.ENTER)
            time.sleep(1)

            # 텍스트가 남아있다면 엔터가 씹힌 것 (수동 클릭 로직 강화)
            if driver.execute_script(
                "return arguments[0].innerText.trim().length > 0;", input_box
            ):
                print("⚠️ 엔터 전송 실패 감지. 전송 버튼을 수동으로 클릭합니다.")
                try:
                    # XPath를 더 정밀하게 수정 (제미나이의 실제 보내기 버튼 속성 타겟팅)
                    send_btn_xpath = "//button[contains(@aria-label, '메시지 보내기') or contains(@aria-label, 'Send message')]"

                    wait.until(EC.element_to_be_clickable((By.XPATH, send_btn_xpath)))
                    send_btns = driver.find_elements(By.XPATH, send_btn_xpath)

                    clicked = False
                    for btn in send_btns:
                        if btn.is_displayed() and btn.is_enabled():
                            # 일반 클릭이 안 먹힐 수 있으므로 ActionChains 활용
                            ActionChains(driver).move_to_element(btn).click(
                                btn
                            ).perform()
                            clicked = True
                            break

                    if not clicked:
                        print("❌ 화면에 활성화된 전송 버튼을 찾지 못했습니다.")
                except Exception as e:
                    print(f"❌ 수동 전송 버튼 클릭 중 에러: {e}")

            # 전송 후 입력창이 비워질 때까지 최대 5초 대기 (확실한 전송 보장)
            for _ in range(10):
                if driver.execute_script(
                    "return arguments[0].innerText.trim().length == 0;", input_box
                ):
                    print("✅ 질문 전송 확인 완료! (입력창 비워짐)")
                    break
                time.sleep(0.5)

            # --------------------------------------------------
            # 4. 답변 완료 대기
            # --------------------------------------------------
            wait_for_response(driver)

        except Exception as e:
            print(f"❌ 작업 [{index + 1}] 처리 중 에러 발생: {e}")


def start_gemini_manual_session():
    # 필요시 주석 해제하여 기존 크롬 프로세스 정리
    # kill_chrome_processes()

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

        # =====================================================
        # 모델 선택 (상수 값 기반 키보드 제어 방식)
        # =====================================================
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

            model_btn = None
            for btn in model_btns:
                if btn.is_displayed():
                    model_btn = btn
                    break

            if model_btn:
                driver.execute_script("arguments[0].click();", model_btn)
                time.sleep(1)  # 메뉴 렌더링 대기

                print(
                    f"⌨️ 키보드를 사용하여 {TARGET_MODEL_INDEX}번째 모델로 이동합니다..."
                )
                actions = ActionChains(driver)

                # 🔄 [핵심 계산]: 지정한 순서(상수)에 맞춰 아래 방향키 횟수 계산
                # 1번째 모델이면 0번 다운, 2번째 모델이면 1번 다운, 3번째 모델이면 2번 다운
                press_count = max(0, TARGET_MODEL_INDEX - 1)

                for _ in range(press_count):
                    actions.send_keys(Keys.ARROW_DOWN).pause(0.2)

                # 최종 엔터 선택
                actions.send_keys(Keys.ENTER).perform()
                print(f"✅ {TARGET_MODEL_INDEX}번째 모델 선택 명령 완료!")
                time.sleep(2)

            else:
                print("⚠️ 화면에 보이는 모델 드롭다운 버튼을 찾지 못했습니다.")

        except Exception as e:
            print(f"⚠️ 모델 선택 실패: {e}")

        # =====================================================
        # 큐(Queue) 작업 리스트 정의
        # =====================================================
        my_tasks = [
            {
                "prompt": "안녕, 내가 올린 파이썬 코드를 분석해주고, 시간 복잡도를 알려줘.",
                "file_path": "test_code.py",  # 같은 경로에 파일 필요
                "new_chat": True,
            },
            {
                "prompt": "위 코드에서 발생할 수 있는 보안 취약점이나 버그는 없을까?",
                "file_path": None,
                "new_chat": False,
            },
            {
                "prompt": "주제를 바꿔서, PyQt5로 창을 띄우는 제일 간단한 기본 예제 코드를 짜줘.",
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

    finally:
        pass


if __name__ == "__main__":
    start_gemini_manual_session()