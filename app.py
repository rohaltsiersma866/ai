import streamlit as st
import requests
import json
import base64
import io
from PIL import Image
import os
from typing import Optional, List, Dict
import time
import uuid

# Cấu hình trang
st.set_page_config(
    page_title="AI Chat Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS tùy chỉnh giống Claude.ai
st.markdown("""
<style>
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Main container */
    .main > div {
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    
    /* Header */
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem 2rem;
        color: white;
        border-radius: 0 0 15px 15px;
        margin-bottom: 2rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    /* Chat container */
    .chat-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 0 1rem;
    }
    
    /* Message bubbles */
    .message-container {
        display: flex;
        margin: 1.5rem 0;
        align-items: flex-start;
    }
    
    .user-message {
        flex-direction: row-reverse;
    }
    
    .message-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        margin: 0 12px;
        flex-shrink: 0;
    }
    
    .user-avatar {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    .assistant-avatar {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
    }
    
    .message-bubble {
        max-width: 70%;
        padding: 12px 16px;
        border-radius: 18px;
        font-size: 0.95rem;
        line-height: 1.4;
        word-wrap: break-word;
    }
    
    .user-bubble {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-bottom-right-radius: 8px;
    }
    
    .assistant-bubble {
        background: #f8f9fa;
        color: #333;
        border: 1px solid #e9ecef;
        border-bottom-left-radius: 8px;
    }
    
    /* Input area */
    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        border-top: 1px solid #e9ecef;
        padding: 1rem 2rem;
        z-index: 1000;
    }
    
    .input-wrapper {
        max-width: 800px;
        margin: 0 auto;
        display: flex;
        gap: 0.5rem;
        align-items: flex-end;
    }
    
    /* File upload area */
    .file-upload {
        background: #f8f9fa;
        border: 2px dashed #dee2e6;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
        transition: all 0.3s ease;
    }
    
    .file-upload:hover {
        border-color: #667eea;
        background: #f0f4ff;
    }
    
    /* Model selector */
    .model-selector {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1001;
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        padding: 0.5rem;
    }
    
    /* Typing indicator */
    .typing-indicator {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        background: #f8f9fa;
        border-radius: 18px;
        border-bottom-left-radius: 8px;
        max-width: 100px;
        margin-left: 52px;
    }
    
    .typing-dots {
        display: flex;
        gap: 4px;
    }
    
    .typing-dot {
        width: 8px;
        height: 8px;
        background: #999;
        border-radius: 50%;
        animation: typing 1.4s infinite ease-in-out;
    }
    
    .typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .typing-dot:nth-child(2) { animation-delay: -0.16s; }
    
    @keyframes typing {
        0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
        40% { transform: scale(1); opacity: 1; }
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .message-bubble {
            max-width: 85%;
        }
        
        .input-container {
            padding: 1rem;
        }
        
        .model-selector {
            position: relative;
            top: auto;
            right: auto;
            margin-bottom: 1rem;
        }
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 3px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #a1a1a1;
    }
    
    /* Welcome screen */
    .welcome-screen {
        text-align: center;
        padding: 4rem 2rem;
        max-width: 600px;
        margin: 0 auto;
    }
    
    .welcome-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    
    .welcome-subtitle {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
        line-height: 1.6;
    }
    
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin-top: 3rem;
    }
    
    .feature-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        transition: transform 0.2s ease;
    }
    
    .feature-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    
    .feature-icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    
    /* Content spacing for fixed input */
    .main-content {
        padding-bottom: 120px;
    }
</style>
""", unsafe_allow_html=True)

class AgentRouterAPI:
    def __init__(self, api_key: str, base_url: str = "https://agentrouter.org"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_available_models(self) -> List[Dict]:
        """Lấy danh sách các model có sẵn từ AgentRouter"""
        models = [
            {
                "id": "claude-sonnet-4-20250514",
                "name": "Claude 4 Sonnet",
                "provider": "Anthropic",
                "description": "Mô hình Claude mới nhất, cân bằng giữa hiệu suất và tốc độ",
                "capabilities": ["text", "vision", "code", "analysis"]
            },
            {
                "id": "claude-opus-4-20250514", 
                "name": "Claude 4 Opus",
                "provider": "Anthropic",
                "description": "Mô hình Claude mạnh nhất, tối ưu cho các tác vụ phức tạp",
                "capabilities": ["text", "vision", "code", "analysis", "reasoning"]
            },
            {
                "id": "claude-opus-4-1-20250805",
                "name": "Claude 4.1 Opus", 
                "provider": "Anthropic",
                "description": "Phiên bản cải tiến của Claude 4 Opus với hiệu suất vượt trội",
                "capabilities": ["text", "vision", "code", "analysis", "reasoning"]
            },
            {
                "id": "claude-3-5-haiku-20241022",
                "name": "Claude 3.5 Haiku",
                "provider": "Anthropic", 
                "description": "Mô hình Claude nhỏ gọn, tốc độ cao cho các tác vụ cơ bản",
                "capabilities": ["text", "code"]
            },
            {
                "id": "gpt-5",
                "name": "GPT-5",
                "provider": "OpenAI",
                "description": "Mô hình GPT thế hệ mới nhất từ OpenAI",
                "capabilities": ["text", "vision", "code", "analysis", "reasoning"]
            },
            {
                "id": "glm-4.5",
                "name": "GLM-4.5",
                "provider": "Zhipu AI",
                "description": "Mô hình AI tiên tiến từ Zhipu AI với khả năng đa ngôn ngữ",
                "capabilities": ["text", "vision", "code", "multilingual"]
            }
        ]
        return models
    
    def encode_image_to_base64(self, image_file) -> str:
        """Chuyển đổi ảnh thành base64"""
        if isinstance(image_file, Image.Image):
            buffer = io.BytesIO()
            image_file.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
        else:
            image_bytes = image_file.read()
            # Reset file pointer for display
            image_file.seek(0)
        
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def process_file_content(self, file) -> Dict:
        """Xử lý nội dung file"""
        file_info = {
            "name": file.name,
            "type": file.type,
            "size": file.size,
            "id": str(uuid.uuid4())
        }
        
        # Xử lý file ảnh
        if file.type.startswith('image/'):
            try:
                file_info["content"] = self.encode_image_to_base64(file)
                file_info["media_type"] = file.type
                file_info["category"] = "image"
                return file_info
            except Exception as e:
                st.error(f"❌ Lỗi xử lý ảnh: {e}")
                return None
        
        # Xử lý file text
        elif file.type in ['text/plain', 'application/json', 'text/csv']:
            try:
                content = file.read().decode('utf-8')
                file_info["content"] = content
                file_info["category"] = "text"
                return file_info
            except Exception as e:
                st.error(f"❌ Lỗi xử lý file: {e}")
                return None
        
        # Xử lý file PDF
        elif file.type == 'application/pdf':
            file_info["content"] = "PDF file - Nội dung sẽ được xử lý bởi AI"
            file_info["category"] = "document"
            return file_info
        
        return file_info
    
    def create_message_with_files(self, text: str, files: List[Dict]) -> List[Dict]:
        """Tạo message với file đính kèm"""
        content = []
        
        # Thêm text
        if text:
            content.append({
                "type": "text",
                "text": text
            })
        
        # Thêm files
        for file_info in files:
            if file_info["category"] == "image":
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file_info["media_type"],
                        "data": file_info["content"]
                    }
                })
            elif file_info["category"] == "text":
                content.append({
                    "type": "text", 
                    "text": f"\n\n📄 **File: {file_info['name']}**\n```\n{file_info['content'][:2000]}{'...' if len(file_info['content']) > 2000 else ''}\n```"
                })
            else:
                content.append({
                    "type": "text",
                    "text": f"\n\n📎 **Đã đính kèm file**: {file_info['name']} ({file_info['type']})"
                })
        
        return content
    
    def chat_completion(self, messages: List[Dict], model: str = "claude-sonnet-4-20250514", 
                       max_tokens: int = 4000, temperature: float = 0.7) -> Optional[Dict]:
        """Gửi request chat completion tới AgentRouter"""
        try:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
            
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"API Error {response.status_code}"
                try:
                    error_detail = response.json()
                    if "error" in error_detail:
                        error_msg += f": {error_detail['error'].get('message', response.text)}"
                except:
                    error_msg += f": {response.text}"
                
                st.error(f"❌ {error_msg}")
                return None
                
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timeout. Vui lòng thử lại.")
            return None
        except requests.exceptions.RequestException as e:
            st.error(f"🌐 Network error: {e}")
            return None
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
            return None

def render_message(message: Dict, model_name: str = ""):
    """Render một tin nhắn chat"""
    role = message["role"]
    content = message["content"]
    
    # Extract text content
    if isinstance(content, list):
        text_content = ""
        for item in content:
            if item.get("type") == "text":
                text_content += item.get("text", "")
    else:
        text_content = content
    
    if role == "user":
        st.markdown(f"""
        <div class="message-container user-message">
            <div class="message-avatar user-avatar">👤</div>
            <div class="message-bubble user-bubble">
                {text_content.replace('\n', '<br>')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="message-container">
            <div class="message-avatar assistant-avatar">🤖</div>
            <div class="message-bubble assistant-bubble">
                <div style="font-size: 0.8rem; color: #666; margin-bottom: 0.5rem;">
                    {model_name}
                </div>
                {text_content.replace('\n', '<br>')}
            </div>
        </div>
        """, unsafe_allow_html=True)

def show_typing_indicator():
    """Hiển thị typing indicator"""
    st.markdown("""
    <div class="typing-indicator">
        <div class="typing-dots">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_welcome_screen():
    """Render màn hình chào mừng"""
    st.markdown("""
    <div class="welcome-screen">
        <div class="welcome-title">🤖 AI Chat Assistant</div>
        <div class="welcome-subtitle">
            Trò chuyện thông minh với các AI model hàng đầu thế giới<br>
            Claude 4, GPT-5, GLM-4.5 và nhiều hơn nữa
        </div>
        
        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-icon">🧠</div>
                <h3>Đa AI Model</h3>
                <p>Truy cập Claude 4, GPT-5, GLM-4.5 trong một ứng dụng</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">👀</div>
                <h3>Nhìn & Hiểu</h3>
                <p>AI có thể xem ảnh và hiểu nội dung hình ảnh</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📁</div>
                <h3>Xử lý File</h3>
                <p>Upload và phân tích file text, JSON, CSV, PDF</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⚡</div>
                <h3>Tốc độ Cao</h3>
                <p>Phản hồi nhanh chóng và chính xác</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def main():
    # Khởi tạo session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "files" not in st.session_state:
        st.session_state.files = []
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "claude-sonnet-4-20250514"
    
    # Header
    st.markdown("""
    <div class="header-container">
        <h1 style="margin: 0; font-size: 1.8rem; font-weight: 600;">
            🤖 AI Chat Assistant
        </h1>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">
            Powered by AgentRouter - Truy cập Claude 4, GPT-5, GLM-4.5
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # API Key và Model selector trong sidebar ẩn
    with st.sidebar:
        st.header("⚙️ Cấu hình")
        
        # API Key
        api_key = st.text_input(
            "AgentRouter API Key", 
            value=st.session_state.api_key,
            type="password", 
            help="Lấy từ https://agentrouter.org/console/token"
        )
        st.session_state.api_key = api_key
        
        if api_key:
            # Model selection
            api_client = AgentRouterAPI(api_key)
            models = api_client.get_available_models()
            
            st.subheader("🤖 Chọn AI Model")
            for model in models:
                if st.button(
                    f"{model['name']}", 
                    key=model['id'],
                    help=model['description'],
                    use_container_width=True
                ):
                    st.session_state.selected_model = model['id']
            
            # Hiển thị model đang chọn
            current_model = next((m for m in models if m['id'] == st.session_state.selected_model), models[0])
            st.info(f"🎯 **Đang sử dụng**: {current_model['name']}")
            
            # Parameters
            st.subheader("🎛️ Tham số")
            temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
            max_tokens = st.slider("Max Tokens", 100, 8000, 4000, 100)
            
            # Clear chat
            if st.button("🗑️ Xóa lịch sử", use_container_width=True):
                st.session_state.messages = []
                st.session_state.files = []
                st.rerun()
    
    # Main content
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    
    if not st.session_state.api_key:
        st.warning("🔑 Vui lòng nhập AgentRouter API Key trong sidebar để bắt đầu!")
        render_welcome_screen()
    else:
        # Model selector nổi
        api_client = AgentRouterAPI(st.session_state.api_key)
        models = api_client.get_available_models()
        current_model = next((m for m in models if m['id'] == st.session_state.selected_model), models[0])
        
        model_options = [f"{m['name']} ({m['provider']})" for m in models]
        model_ids = [m['id'] for m in models]
        current_index = model_ids.index(st.session_state.selected_model)
        
        selected_index = st.selectbox(
            "🤖 AI Model",
            range(len(models)),
            index=current_index,
            format_func=lambda x: model_options[x],
            key="model_selector"
        )
        
        if model_ids[selected_index] != st.session_state.selected_model:
            st.session_state.selected_model = model_ids[selected_index]
            st.rerun()
        
        # File upload
        with st.expander("📎 Upload File/Ảnh", expanded=False):
            uploaded_files = st.file_uploader(
                "Chọn file để AI phân tích",
                accept_multiple_files=True,
                type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'txt', 'json', 'csv', 'pdf'],
                key="file_uploader"
            )
            
            if uploaded_files:
                st.session_state.files = []
                cols = st.columns(min(len(uploaded_files), 4))
                
                for i, file in enumerate(uploaded_files):
                    processed_file = api_client.process_file_content(file)
                    if processed_file:
                        st.session_state.files.append(processed_file)
                        
                        with cols[i % 4]:
                            if file.type.startswith('image/'):
                                st.image(file, width=150)
                            st.caption(f"📄 {file.name}")
        
        # Chat messages
        chat_container = st.container()
        
        with chat_container:
            if not st.session_state.messages:
                render_welcome_screen()
            else:
                for message in st.session_state.messages:
                    render_message(message, current_model['name'])
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Chat input (fixed at bottom)
    if st.session_state.api_key:
        user_input = st.chat_input("💬 Nhập tin nhắn của bạn...", key="chat_input")
        
        if user_input:
            # Add user message
            if st.session_state.files:
                message_content = api_client.create_message_with_files(user_input, st.session_state.files)
            else:
                message_content = user_input
            
            user_message = {"role": "user", "content": message_content}
            st.session_state.messages.append(user_message)
            
            # Show typing indicator
            with st.empty():
                show_typing_indicator()
                time.sleep(1)  # Brief pause for UX
            
            # Get AI response
            try:
                response = api_client.chat_completion(
                    messages=st.session_state.messages,
                    model=st.session_state.selected_model,
                    max_tokens=max_tokens if 'max_tokens' in locals() else 4000,
                    temperature=temperature if 'temperature' in locals() else 0.7
                )
                
                if response and "choices" in response:
                    assistant_message = response["choices"][0]["message"]["content"]
                    st.session_state.messages.append({"role": "assistant", "content": assistant_message})
                    
                    # Clear files after sending
                    st.session_state.files = []
                else:
                    st.error("❌ Không nhận được phản hồi từ AI. Vui lòng thử lại.")
            
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")
            
            st.rerun()

if __name__ == "__main__":
    main()
