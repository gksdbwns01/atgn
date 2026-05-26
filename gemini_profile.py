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
            # =====================================================
            # 💡 [추가된 로직] Deep Research일 경우 강제로 새 채팅 활성화
            # =====================================================
            if task.get("attachment_action") == "Deep Research" and not task.get(
                "new_chat"
            ):
                print(
                    "💡 'Deep Research' 옵션이 감지되어 강제로 '새 채팅'을 시작합니다."
                )
                task["new_chat"] = True  # 값을 강제로 True로 덮어씌움
            # =====================================================
            # 1. 새 채팅(new_chat) 처리 로직 추가 (여기를 추가하세요!)
            # =====================================================
            if task.get("new_chat"):
                print("✨ '새 채팅'을 시작합니다...")
                try:
                    # '새 채팅' 버튼을 찾는 XPath (한국어/영어 대응 및 구조 변경 대비)
                    new_chat_xpath = (
                        "//button[contains(@aria-label, '새 채팅') or "
                        "contains(@aria-label, 'New chat') or "
                        "contains(., '새 채팅')]"
                    )
                    wait.until(
                        EC.presence_of_element_located((By.XPATH, new_chat_xpath))
                    )
                    new_chat_btns = driver.find_elements(By.XPATH, new_chat_xpath)

                    clicked_new_chat = False
                    for btn in new_chat_btns:
                        if btn.is_displayed():
                            click_safely(driver, btn)
                            clicked_new_chat = True
                            print("✅ '새 채팅' 버튼 클릭 완료")
                            time.sleep(2)  # UI가 초기화될 때까지 잠시 대기
                            break

                    if not clicked_new_chat:
                        print("⚠️ 화면에서 '새 채팅' 버튼을 찾을 수 없습니다.")

                except Exception as e:
                    print(f"⚠️ '새 채팅' 버튼 클릭 중 에러 발생: {e}")
            # 2. 첨부 메뉴 액션 처리
            action_name = task.get("attachment_action")
            file_path = task.get("file_path")

            # [1단계] 업로드할 파일이 있다면 우선적으로 파일 업로드 진행
            if file_path:
                print("📂 파일 업로드 시도 중...")
                try:
                    # ➕(첨부) 버튼 클릭
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

                    # 파일 경로 리스트 변환 및 검증
                    file_paths = (
                        file_path if isinstance(file_path, list) else [file_path]
                    )
                    valid_paths = []
                    for fp in file_paths:
                        abs_path = os.path.abspath(fp)
                        if not os.path.exists(abs_path):
                            print(f"⚠️ 에러: 업로드할 파일 없음. 경로: {abs_path}")
                        else:
                            valid_paths.append(abs_path)

                    if not valid_paths:
                        print("❌ 유효한 파일이 없어 업로드를 취소합니다.")
                    else:
                        # 무조건 '파일 업로드' 메뉴 클릭
                        upload_menu_xpath = (
                            "//*[(self::div or self::span or self::button or self::li) "
                            "and contains(text(), '파일 업로드')]"
                        )
                        wait.until(
                            EC.presence_of_element_located(
                                (By.XPATH, upload_menu_xpath)
                            )
                        )
                        menu_items = driver.find_elements(By.XPATH, upload_menu_xpath)

                        clicked_menu = False
                        for item in reversed(menu_items):
                            if item.is_displayed():
                                click_safely(driver, item)
                                clicked_menu = True
                                break

                        if not clicked_menu:
                            print("❌ 화면에서 '파일 업로드' 메뉴를 찾을 수 없습니다.")
                        else:
                            print("📂 윈도우 열기 창 팝업 대기 중...")
                            time.sleep(2)

                            desktop = Desktop(backend="win32")
                            dialog = desktop.window(
                                title_re=".*열기.*|.*Open.*|.*업로드.*",
                                class_name="#32770",
                            )
                            dialog.wait("visible", timeout=15)
                            dialog.set_focus()
                            time.sleep(0.5)

                            # 다중 파일 업로드를 위한 포맷팅
                            file_name_edit = dialog.child_window(class_name="Edit")
                            formatted_paths = " ".join([f'"{p}"' for p in valid_paths])
                            file_name_edit.set_edit_text(formatted_paths)
                            time.sleep(1)

                            dialog.type_keys("{ENTER}")
                            print("✅ 파일 선택 완료")

                            # 파일 업로드 완료 대기
                            print(
                                "⏳ 파일들이 웹 페이지에 완전히 업로드되기를 대기합니다..."
                            )
                            upload_wait = WebDriverWait(driver, 60)
                            for valid_path in valid_paths:
                                file_basename = os.path.basename(valid_path)
                                file_chip_xpath = f"//*[contains(text(), '{file_basename}') or contains(@aria-label, '{file_basename}')]"
                                upload_wait.until(
                                    EC.presence_of_element_located(
                                        (By.XPATH, file_chip_xpath)
                                    )
                                )
                                print(f"✅ '{file_basename}' 업로드 완료 확인!")
                            time.sleep(1.5)

                except Exception as e:
                    print(f"⚠️ 파일 업로드 실패: {e}")

            # [2단계] 파일 업로드 외의 기타 액션 (Canvas, Deep Research 등) 실행
            if action_name and action_name != "파일 업로드":
                print(f"🚀 추가 메뉴 동작 시도: {action_name}")
                try:
                    # 메뉴가 닫혔을 수 있으므로 ➕(첨부) 버튼 다시 클릭
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

                    # 도구 더보기 서브메뉴 처리
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

                    # 지정된 action_name 클릭
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
                    print(f"⚠️ 추가 메뉴 조작 실패: {e}")

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
                "prompt": "이 코드에 현재시간을 출력하는 코드를 추가해줘.",
                "attachment_action": "Canvas",
                "file_path": r"C:\Users\gksdbwns\Desktop\secupro\ge\gemini_profile\test_code.py",
                "new_chat": True,
            },
            {
                "prompt": "이 코드에 주석을 자세히 추가해줘",
                "attachment_action": None,
                "file_path": None,
                "new_chat": False,
            },
            {
                "prompt": "내가 올린 파이썬 코드들의 차이점을 설명해줘",
                "attachment_action": "파일 업로드",
                "file_path": [
                    r"C:\Users\gksdbwns\yolo01\gmpy\v4b.py",
                    r"C:\Users\gksdbwns\yolo01\gmpy\v4.py",
                ],
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
