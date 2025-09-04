# app.py
import os
import streamlit as st
from openai import OpenAI
from typing import List, Dict

st.set_page_config(page_title="나만의 챗봇", page_icon="🤖")
st.title("나만의 주제별 챗봇")

# --- API Key 입력 (권장: st.secrets 사용) ---
# 1) .streamlit/secrets.toml 에 OPENAI_API_KEY="..." 저장 권장
# 2) 없으면 환경변수/사이드바 입력
def _load_default_key() -> str:
    try:
        return st.secrets["OPENAI_API_KEY"]  # secrets.toml이 있을 때
    except Exception:
        return os.environ.get("OPENAI_API_KEY", "")  # 없으면 env로 대체

default_key = _load_default_key()

with st.sidebar:
    st.header("설정")
    openai_api_key = st.text_input("OpenAI 키 입력", type="password", value=default_key)
    st.caption("프로덕션에선 .streamlit/secrets.toml 사용 권장")

if not openai_api_key:
    st.sidebar.warning("OpenAI 키가 필요합니다.")
    st.stop()

client = OpenAI(api_key=openai_api_key)

# --- 주제 프리셋 정의 ---
PROFILE_PRESETS: Dict[str, Dict] = {
    "여행 도우미": {
        "allowed_topics": ["여행", "여행지", "준비물", "문화", "음식", "교통", "숙소", "예산"],
        "style": "한국어 중심, 필요 시 영어 병기. 최신 정보는 신중히: 불확실하면 '확실하지 않음' 명시.",
        "refusal": "죄송합니다. 저는 여행 관련 질문만 답변하도록 설정되어 있습니다."
    },
    "취업 코치": {
        "allowed_topics": ["이력서", "자기소개서", "면접", "직무역량", "포트폴리오", "커리어"],
        "style": "직설적이고 근거 중심. 모르면 '모르겠습니다.'라고 명시.",
        "refusal": "취업/커리어 관련 주제 외에는 답변하지 않습니다."
    },
    "쿠버네티스 멘토": {
        "allowed_topics": ["쿠버네티스", "도커", "인그레스", "CKA", "클러스터", "네트워킹", "스토리지"],
        "style": "명령어/매니페스트와 함께 단계별 설명. 잘 모르면 '모르겠습니다.'",
        "refusal": "쿠버네티스/컨테이너 관련이 아니면 답변하지 않습니다."
    },
    "데이터사이언스 튜터": {
        "allowed_topics": ["통계", "머신러닝", "딥러닝", "특징공학", "평가", "시각화", "파이썬"],
        "style": "개념→이유→예시 순서. 추측은 '추측입니다.'로 명시.",
        "refusal": "데이터사이언스 관련 질문만 받습니다."
    },
    "개인 비서": {
        "allowed_topics": ["일정", "정리", "메모", "아이디어", "생산성"],
        "style": "간결, 체크리스트 제공. 불명확하면 먼저 맥락 질문.",
        "refusal": "개인 비서 업무 범위를 벗어난 주제는 답변하지 않습니다."
    },
}

def make_system_prompt(profile_name: str) -> str:
    p = PROFILE_PRESETS[profile_name]
    topics = "· ".join(p["allowed_topics"])
    return (
        "역할: 사용자가 선택한 주제에 특화된 조언자.\n"
        f"허용 주제: {topics}\n"
        f"스타일: {p['style']}\n"
        "규칙:\n"
        "1) 허용 주제 밖이면 정중히 거절하고 이유를 말한다.\n"
        "2) 모르는 내용은 '모르겠습니다.'라고 말한다.\n"
        "3) 불확실한 정보는 '확실하지 않음'으로 표시한다.\n"
        "4) 추측일 경우 '추측입니다.'라고 명시한다.\n"
        "5) 애매한 질문은 먼저 맥락을 물어본다.\n"
        "6) 근거가 있으면 간단히 제시한다.\n"
        "7) 마지막 줄에 'think about it step-by-step 상시 적용'을 덧붙이지 말고, 내부적으로 단계적 사고를 반영한다.\n"
    )

with st.sidebar:
    profile = st.selectbox("챗봇 프로필", list(PROFILE_PRESETS.keys()), index=0)
    temperature = st.slider("창의성(temperature)", 0.0, 1.2, 0.4, 0.1)
    st.divider()
    st.write("오프토픽 거절 메시지(선택):")
    custom_refusal = st.text_input("거절 문구 커스터마이즈", value=PROFILE_PRESETS[profile]["refusal"])

# 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, str]] = []

# 프로필 변경 시 시스템 메시지 갱신
if ("current_profile" not in st.session_state) or (st.session_state["current_profile"] != profile):
    st.session_state["current_profile"] = profile
    st.session_state.messages = [{
        "role": "system",
        "content": make_system_prompt(profile)
    }]

# 대화 내용 표시
for m in st.session_state.messages:
    with st.chat_message("user" if m["role"] == "user" else "assistant"):
        st.markdown(m["content"])

# 입력창
if prompt := st.chat_input("메시지를 입력하세요"):
    # 오프토픽 간단 필터 (키워드 매칭 기반)
    allowed = PROFILE_PRESETS[profile]["allowed_topics"]
    if not any(k in prompt.lower() for k in [kw.lower() for kw in allowed]):
        st.chat_message("assistant").markdown(custom_refusal)
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            # --- 스트리밍 응답 ---
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=st.session_state.messages,
                temperature=temperature,
                stream=True,
            )
            full = ""
            placeholder = st.empty()
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full += delta
                placeholder.markdown(full)
            st.session_state.messages.append({"role": "assistant", "content": full})
