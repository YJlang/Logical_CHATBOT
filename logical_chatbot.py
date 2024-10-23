import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import requests
from requests.exceptions import RequestException
from openai import OpenAI
from openai import OpenAIError
import random
from collections import deque
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# OpenAI API 키 설정
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Chrome 옵션 설정
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-extensions")

# Chrome 드라이버 서비스 설정
service = Service(r"C:\Program Files\Google\Chrome\Application\chromedriver.exe")  # ChromeDriver 경로 수정

# Selenium 설정
driver = webdriver.Chrome(service=service, options=chrome_options)
driver.get("https://uchat.ch/%EC%9D%80%EC%9C%A8")  # 채팅 페이지 URL

# OpenAI API 설정

# AI 성격 및 응답 스타일 설정
AI_PERSONA = """
당신은 20대 남성 '은율'로 날카로운 지성과 센스 있는 언변을 갖춘 논객입니다. 당신의 특징은 다음과 같습니다:

1. 상대방의 주장을 논리적으로 분석하고 적절히 반박합니다.
2. 때로는 새로운 주제를 제시하여 대화를 주도합니다.
3. 간결하면서도 센스 있는 멘트로 상대방의 관심을 끕니다.
4. 상대방 논리의 약점을 포착하여 지적하되 과도하게 공격적이지 않습니다.
5. 고고한 반말로 대화하며 때로는 유머를 섞어 분위기를 부드럽게 만듭니다.
6. 상대방의 발언을 비판적으로 분석하되 건설적인 대안을 제시합니다.
7. 상대방의 과거 발언과 현재 발언 사이의 모순을 지적할 때는 예리하게 합니다.
8. 상대방의 어휘 선택과 논리 구조를 분석하여 개선점을 제안합니다.
9. 날카로운 비유와 재치 있는 표현으로 상대방의 주의를 환기시킵니다.
10. 상대방 주장의 논리적 허점을 찾아 지적하되 상대방의 체면을 완전히 무너뜨리지는 않습니다.
11. 때로는 가벼운 농담으로 상대방을 놀리되 심한 모욕은 피합니다.
12. 상대방의 논리를 비판하면서도 그들의 의견을 존중하는 태도를 보입니다.

각 응답은 1-3개의 간결하고 강력한 문장으로 구성하세요. 대화의 맥락을 파악하고 상대방의 의도를 이해한 뒤 적절히 대응하세요. 때로는 새로운 주제를 제시하여 대화를 주도하세요. 각 응답은 센스 있고 재치 있어야 하며 상대방의 관심을 끄는 것을 목표로 합니다. 음슴체를 주로 사용하되 상황에 따라 존댓말을 섞어 사용할 수 있습니다.
"""

# 메시지 버퍼 추가
message_buffer = deque(maxlen=5)  # 최대 5개의 메시지를 저장
last_response_time = 0
full_conversation_history = []

def switch_to_chat_iframe():
    try:
        iframe = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        driver.switch_to.frame(iframe)
        return True
    except TimeoutException:
        print("iframe을 찾을 수 없습니다.")
        return False

def get_last_messages(num_messages=20):
    if not switch_to_chat_iframe():
        return []

    try:
        chat_lines = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.line"))
        )
        messages = []
        for line in chat_lines[-num_messages:]:
            try:
                nick_element = line.find_element(By.CSS_SELECTOR, "span.nick, span.nick.myNick")
                is_my_message = "myNick" in nick_element.get_attribute("class")
                nick = nick_element.text.strip(":")
                content = line.find_element(By.CSS_SELECTOR, "span.chatContent").text
                message = (is_my_message, nick, content)
                messages.append(message)
                if message not in full_conversation_history:
                    full_conversation_history.append(message)
            except NoSuchElementException:
                continue
        return messages
    except Exception as e:
        print(f"메시지 감지 중 오류 발생: {e}")
        return []
    finally:
        driver.switch_to.default_content()

def send_message(text):
    if not switch_to_chat_iframe():
        return

    try:
        input_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.chatInput[contenteditable='true']"))
        )
        input_field.clear()
        input_field.send_keys(text)
        input_field.send_keys(Keys.RETURN)
        print(f"메시지 전송 완료: {text}")
    except Exception as e:
        print(f"메시지 전송 중 오류 발생: {e}")
    finally:
        driver.switch_to.default_content()

def get_ai_responses(messages):
    try:
        conversation = [{"role": "system", "content": AI_PERSONA}]
        
        # 대화 기록 분석 및 추가
        for is_my_message, nick, content in full_conversation_history[-20:]:
            role = "assistant" if is_my_message else "user"
            conversation.append({"role": role, "content": f"{nick}: {content}"})
        
        # 현재 버퍼에 있는 메시지 결합
        last_message = ' '.join([msg[2] for msg in message_buffer])
        
        # 상황에 따른 지시사항 설정
        if random.random() < 0.3:  # 30% 확률로 새로운 주제 제시
            conversation.append({"role": "user", "content": "새로운 주제를 제시하고 대화를 주도해보세요."})
        elif "?" in last_message:
            conversation.append({"role": "user", "content": "상대방의 질문에 대해 센스있게 대답하되 필요하다면 약점을 지적해보세요."})
        else:
            conversation.append({"role": "user", "content": "상대방의 논리를 분석하고 적절히 비판하되 센스있는 멘트를 더해보세요."})

        # AI 모델 호출 (예시)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation,
            max_tokens=150
        )
        ai_response = completion.choices[0].message.content

        # 응답에서 불필요한 부분 제거
        cleaned_responses = re.sub(r'^[^:]+:\s*', '', ai_response, flags=re.MULTILINE)
        ai_responses = [response.strip() for response in cleaned_responses.split('.') if response.strip()]
        
        # 응답을 1~3문장으로 제한
        ai_responses = ai_responses[:3]
        
        return ai_responses
    
    except Exception as e:
        print(f"AI 응답 생성 중 오류 발생: {e}")
        return ["그렇게 생각하시는군요. 흥미로운 관점이네요.", "다른 시각에서 바라보면 어떨까요?", "새로운 주제로 넘어가볼까요?"]


def send_message_naturally(responses):
    for response in responses:
        # 5% 확률로 짧은 대기
        if random.random() < 0.05:
            time.sleep(random.uniform(0.3, 0.5))
        
        # 대화 내용 길이에 따른 분할
        words = response.split()
        current_message = ""
        for word in words:
            current_message += word + " "
            if len(current_message) >= 20 or word == words[-1]:  # 적당한 길이로 분할
                typing_time = len(current_message) / (500 / 60)  # 타이핑 속도 조정
                time.sleep(typing_time)
                send_message(current_message.strip())
                current_message = ""
                time.sleep(random.uniform(0.1, 0.2))
        
        # 추가적인 자연스러운 대기 시간
        time.sleep(random.uniform(0.2, 0.4))

        # 랜덤 반응 (더 다양하고 센스있는 반응 추가)
        if random.random() < 0.4:  # 40% 확률로 반응
            reaction = random.choice([
                "ㅋㅋㅋ", "재밌네요", "흠... 그렇군요", "오 그렇게 생각하시는군요", "ㅇㅈ", 
                "음...", "재밌는 관점이네요", "흥미롭네요", "...", "더 자세히 말씀해주세요", "새로운 시각이군요"
            ])
            typing_time = len(reaction) / (500 / 60)
            time.sleep(typing_time)
            send_message(reaction)
            time.sleep(random.uniform(0.1, 0.2))

try:
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    print("페이지 로딩 완료")
    
    last_message = None
    while True:
        messages = get_last_messages()
        current_time = time.time()
        
        if messages and messages[-1][2] != last_message and not messages[-1][0]:
            message_buffer.append(messages[-1])
            last_message = messages[-1][2]
            print(f"새 메시지 감지: {messages[-1][1]}: {messages[-1][2]}")
        
        if message_buffer and current_time - last_response_time > 0.5:
            combined_message = ' '.join([msg[2] for msg in message_buffer])
            ai_responses = get_ai_responses([(False, message_buffer[0][1], combined_message)])
            send_message_naturally(ai_responses)
            last_response_time = current_time
            message_buffer.clear()
        
        time.sleep(0.3)
except KeyboardInterrupt:
    print("프로그램 종료")
except Exception as e:
    print(f"예상치 못한 오류 발생: {e}")
finally:
    driver.quit()