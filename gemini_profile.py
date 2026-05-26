import os
import time

import psutil
import undetected_chromedriver as uc
from pywinauto import Desktop
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# =====================================================
# ⚙️ 사용자 설정 상수
# =====================================================
TARGET_MODEL_INDEX = 2

SUBMENU_TOOLS = [
    "Canvas",
    "Deep Research",
    "음악 만들기",
    "가이드 학습",
    "개인 인텔리전스",
]


def kill_chrome_processes():
    """충돌 방지를 위해 기존 크롬 프로세스를 종료합니다."""
    for proc in psutil.process_iter(["name"]):
        try:
            if "chrome" in proc.info.get("name", "").lower():
                proc.kill()
        except Exception:
            pass
    time.sleep(1)


def wait_for_response(driver):
    """답변 생성을 대기하는 함수입니다. (최대 10분 타임아웃 적용)"""
    print("⏳ 답변 생성 대기 중... (최대 10분 대기)")
    time.sleep(2)

    stop_btn_xpath = (
        "//button[contains(@aria-label, '중지') or contains(@aria-label, 'Stop')]"
    )

    # 1단계: 답변 생성 시작 감지
    generating_started = False
    for _ in range(40):
        stop_btns = driver.find_elements(By.XPATH, stop_btn_xpath)
        if any(btn.is_displayed() for btn in stop_btns):
            generating_started = True
            print("▶️ 생성 중 상태 확인됨 ('응답 중지' 버튼 감지)")
            break
        time.sleep(0.5)

    # 2단계: 답변 생성 완료 대기 (타임아웃 적용)
    if generating_started:
        start_wait_time = time.time()
        max_wait_time = 600  # 10분 (초 단위)

        while True:
            # 타임아웃 체크 (현재 시간 - 대기 시작 시간)
            elapsed_time = time.time() - start_wait_time
            if elapsed_time > max_wait_time:
                print(
                    f"⚠️ 경고: 답변 생성 대기 시간 초과 ({max_wait_time}초). 무한 루프를 방지하고 다음 작업으로 넘어갑니다."
                )
                break

            stop_btns = driver.find_elements(By.XPATH, stop_btn_xpath)
            if not any(btn.is_displayed() for btn in stop_btns):
                print("✅ 답변 생성 완료 ('응답 중지' 버튼 사라짐)!")
                time.sleep(2)
                break

            time.sleep(1)  # 1초마다 버튼이 사라졌는지 확인
    else:
        print("✅ 답변이 생성 완료되었습니다 ('응답 중지' 버튼 미감지).")
        time.sleep(2)


def click_safely(driver, element):
    """물리적 클릭(ActionChains) 시도 후 실패하면 JS 클릭으로 우회하는 헬퍼 함수"""
    try:
        ActionChains(driver).move_to_element(element).click().perform()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def process_queue(driver, task_queue):
    """정의된 큐(작업 리스트)를 순차적으로 실행하는 함수입니다."""
    wait = WebDriverWait(driver, 20)

    for index, task in enumerate(task_queue):
        print(
            f"\n[{index + 1}/{len(task_queue)}] 📋 작업 시작: {task['prompt'][:20]}..."
        )

        try:
            # 1. 새 채팅 시작 여부 판별
            # 💡 수정 포인트: attachment_action이 'Deep Research'라면 큐의 설정과 무조건 새 채팅(True)으로 취급합니다.
            action_name = task.get("attachment_action")
            is_deep_research = action_name == "Deep Research"
            should_new_chat = task.get("new_chat") or is_deep_research

            if should_new_chat:
                if is_deep_research:
                    print("🔍 Deep Research 작업 감지: 무조건 새 채팅방을 생성합니다.")
                else:
                    print(
                        "🔄 단축키(Ctrl + Shift + O)를 이용하여 새 채팅방을 생성합니다."
                    )

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

            # 2. 첨부 메뉴 액션 처리
            if action_name:
                print(f"🚀 메뉴 동작 시도: {action_name}")
                try:
                    # ➕(첨부) 버튼 클릭 - 더 넓은 범위의 버튼 레이블 포용
                    attach_btn_xpath = (
                        "//button["
                        "contains(@aria-label, '업로드') or "
                        "contains(@aria-label, '첨부') or "
                        "contains(@aria-label, 'Upload') or "
                        "contains(@aria-label, '파일') or "
                        "contains(@aria-label, '추가')"
                        "]"
                    )
                    wait.until(
                        EC.presence_of_element_located((By.XPATH, attach_btn_xpath))
                    )
                    attach_btns = driver.find_elements(By.XPATH, attach_btn_xpath)

                    for btn in attach_btns:
                        if btn.is_displayed():
                            click_safely(driver, btn)
                            break
                    time.sleep(1.5)

                    # 파일 업로드 동작 처리
                    if action_name == "파일 업로드" and task.get("file_path"):
                        file_path = os.path.abspath(task["file_path"])
                        if not os.path.exists(file_path):
                            print(f"⚠️ 에러: 업로드할 파일 없음. 경로: {file_path}")
                            continue

                        menu_item_xpath = (
                            f"//*[(self::div or self::span or self::button or self::li) "
                            f"and contains(text(), '{action_name}')]"
                        )
                        wait.until(
                            EC.presence_of_element_located((By.XPATH, menu_item_xpath))
                        )
                        menu_items = driver.find_elements(By.XPATH, menu_item_xpath)

                        clicked_menu = False
                        for item in reversed(menu_items):
                            if item.is_displayed():
                                click_safely(driver, item)
                                clicked_menu = True
                                break

                        if not clicked_menu:
                            print(
                                f"❌ 화면에서 '{action_name}' 메뉴를 찾을 수 없습니다."
                            )
                            continue

                        print("📂 윈도우 열기 창 팝업 대기 중...")
                        time.sleep(2)

                        try:
                            desktop = Desktop(backend="win32")
                            dialog = desktop.window(
                                title_re=".*열기.*|.*Open.*|.*업로드.*",
                                class_name="#32770",
                            )
                            dialog.wait("visible", timeout=15)
                            dialog.set_focus()
                            time.sleep(0.5)

                            file_name_edit = dialog.child_window(class_name="Edit")
                            file_name_edit.set_edit_text(file_path)
                            time.sleep(1)

                            dialog.type_keys("{ENTER}")
                            print("✅ 파일 선택 완료 (pywinauto win32 제어 성공)")

                            # =========================================================
                            # 💡 개선된 부분: 대용량 파일 업로드 동적 대기 로직
                            # =========================================================
                            print(
                                "⏳ 파일이 웹 페이지에 완전히 업로드되기를 대기합니다..."
                            )
                            try:
                                # 최대 60초까지 넉넉하게 대기합니다. (필요 시 시간 조절 가능)
                                upload_wait = WebDriverWait(driver, 60)

                                # 업로드한 파일의 이름만 추출 (예: test_code.py)
                                file_basename = os.path.basename(file_path)

                                # 파일 이름이 포함된 요소나 텍스트가 화면에 나타날 때까지 대기
                                # (Gemini UI에 첨부된 파일 칩이 생성되는 것을 감지)
                                file_chip_xpath = f"//*[contains(text(), '{file_basename}') or contains(@aria-label, '{file_basename}')]"

                                upload_wait.until(
                                    EC.presence_of_element_located(
                                        (By.XPATH, file_chip_xpath)
                                    )
                                )
                                print(
                                    f"✅ 웹 페이지 파일 업로드 완료 확인! ('{file_basename}' 감지됨)"
                                )
                                time.sleep(
                                    1
                                )  # UI가 완전히 렌더링되고 안정화되도록 1초 추가 대기

                            except Exception as wait_e:
                                print(
                                    f"⚠️ 파일 업로드 완료 대기 중 시간 초과 또는 요소를 찾을 수 없음: {wait_e}"
                                )
                            # =========================================================

                        except Exception as win_e:
                            print(f"❌ OS 파일 열기 창 제어 실패: {win_e}")

                    # 그 외의 첨부 액션(Canvas, Deep Research 등)
                    else:
                        if action_name in SUBMENU_TOOLS:
                            tools_xpath = (
                                "//*[(self::div or self::span or self::button or self::li) "
                                "and contains(text(), '도구 더보기')]"
                            )
                            wait.until(
                                EC.presence_of_element_located((By.XPATH, tools_xpath))
                            )
                            tool_items = driver.find_elements(By.XPATH, tools_xpath)

                            for item in reversed(tool_items):
                                if item.is_displayed():
                                    click_safely(driver, item)
                                    break
                            time.sleep(1)

                        menu_item_xpath = (
                            f"//*[(self::div or self::span or self::button or self::li) "
                            f"and contains(text(), '{action_name}')]"
                        )
                        wait.until(
                            EC.presence_of_element_located((By.XPATH, menu_item_xpath))
                        )
                        menu_items = driver.find_elements(By.XPATH, menu_item_xpath)

                        for item in reversed(menu_items):
                            if item.is_displayed():
                                click_safely(driver, item)
                                break

                        print(f"✅ '{action_name}' 옵션 선택 완료")
                        time.sleep(1.5)

                except Exception as e:
                    print(f"⚠️ 메뉴 조작 실패: {e}")

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
                            click_safely(driver, btn)
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
            model_button_xpath = "//button[contains(., 'Flash') or contains(., 'Lite') or contains(., 'Pro')]"
            wait.until(EC.presence_of_element_located((By.XPATH, model_button_xpath)))
            model_btns = driver.find_elements(By.XPATH, model_button_xpath)

            model_btn = next((btn for btn in model_btns if btn.is_displayed()), None)

            if model_btn:
                click_safely(driver, model_btn)
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
                "file_path": r"C:\Users\gksdbwns\yolo01\gmpy\v4b.py",
                "new_chat": True,
            },
            {
                "prompt": "tlc ssd의 작동 원리에 대해서 심층 분석 보고서를 작성해줘.",
                "attachment_action": "Deep Research",
                "file_path": None,
                "new_chat": False,  # 💡 이제 여기서 False로 명시해도 강제로 True로 바뀝니다.
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
