import streamlit as st
import requests
import json
import base64
import io
from PIL import Image
import os
from typing import Optional, List, Dict
import mimetypes
import tempfile

# Cấu hình trang
st.set_page_config(
    page_title="Multi-AI Chat App",
    page_icon="🤖",
    layout="wide"
)

# CSS tùy chỉnh
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        font-size: 2.5rem;
        margin-bottom: 2rem;
    }
    .model-selector {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .assistant-message {
        background-color: #f3e5f5;
        border-left: 4px solid #9c27b0;
    }
    .file-upload-area {
        border: 2px dashed #ccc;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
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
    
    def get_available_models(self) -> List[str]:
        """Lấy danh sách các model có sẵn"""
        # Danh sách mặc định dựa trên thông tin từ docs
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229", 
            "claude-3-haiku-20240307",
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo",
            "gemini-1.5-pro",
            "gemini-1.5-flash"
        ]
    
    def encode_image_to_base64(self, image_file) -> str:
        """Chuyển đổi ảnh thành base64"""
        if isinstance(image_file, Image.Image):
            buffer = io.BytesIO()
            image_file.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
        else:
            image_bytes = image_file.read()
        
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def process_file_content(self, file) -> Dict:
        """Xử lý nội dung file"""
        file_info = {
            "name": file.name,
            "type": file.type,
            "size": file.size
        }
        
        # Xử lý file ảnh
        if file.type.startswith('image/'):
            try:
                image = Image.open(file)
                file_info["content"] = self.encode_image_to_base64(image)
                file_info["media_type"] = file.type
                return file_info
            except Exception as e:
                st.error(f"Lỗi xử lý ảnh: {e}")
                return None
        
        # Xử lý file text
        elif file.type in ['text/plain', 'application/json', 'text/csv', 'application/pdf']:
            try:
                if file.type == 'application/pdf':
                    # Đối với PDF, chỉ lưu thông tin file
                    file_info["content"] = "PDF file uploaded"
                else:
                    content = file.read().decode('utf-8')
                    file_info["content"] = content
                return file_info
            except Exception as e:
                st.error(f"Lỗi xử lý file: {e}")
                return None
        
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
            if file_info["type"].startswith('image/'):
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file_info["media_type"],
                        "data": file_info["content"]
                    }
                })
            else:
                # Đối với file text, thêm vào text content
                content.append({
                    "type": "text", 
                    "text": f"\n\nFile: {file_info['name']}\nContent: {file_info['content']}"
                })
        
        return content
    
    def chat_completion(self, messages: List[Dict], model: str = "claude-3-5-sonnet-20241022", 
                       max_tokens: int = 4000, temperature: float = 0.7) -> Optional[Dict]:
        """Gửi request chat completion tới AgentRouter"""
        try:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"API Error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            st.error(f"Request error: {e}")
            return None
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            return None

def main():
    st.markdown("<h1 class='main-header'>🤖 Multi-AI Chat App</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Sử dụng AgentRouter để truy cập nhiều AI model</p>", unsafe_allow_html=True)
    
    # Sidebar cấu hình
    with st.sidebar:
        st.header("⚙️ Cấu hình")
        
        # API Key input
        api_key = st.text_input("AgentRouter API Key", type="password", 
                               help="Lấy API key từ https://agentrouter.org/console/token")
        
        if not api_key:
            st.warning("Vui lòng nhập API key để sử dụng")
            return
        
        # Khởi tạo API client
        api_client = AgentRouterAPI(api_key)
        
        # Model selection
        available_models = api_client.get_available_models()
        selected_model = st.selectbox("Chọn AI Model", available_models)
        
        # Parameters
        st.subheader("Tham số")
        temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
        max_tokens = st.slider("Max Tokens", 100, 8000, 4000, 100)
        
        # Clear chat button
        if st.button("🗑️ Xóa lịch sử chat"):
            st.session_state.messages = []
            st.session_state.files = []
            st.rerun()
    
    # Khởi tạo session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "files" not in st.session_state:
        st.session_state.files = []
    
    # File upload area
    st.markdown("<div class='model-selector'>", unsafe_allow_html=True)
    st.subheader("📎 Upload File/Ảnh")
    uploaded_files = st.file_uploader(
        "Chọn file để AI đọc và phân tích",
        accept_multiple_files=True,
        type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'txt', 'json', 'csv', 'pdf']
    )
    
    # Hiển thị file đã upload
    if uploaded_files:
        st.write("**File đã chọn:**")
        processed_files = []
        
        for file in uploaded_files:
            processed_file = api_client.process_file_content(file)
            if processed_file:
                processed_files.append(processed_file)
                
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📄 {file.name}")
                with col2:
                    st.write(f"{file.size} bytes")
                with col3:
                    st.write(file.type)
                
                # Hiển thị preview cho ảnh
                if file.type.startswith('image/'):
                    st.image(file, width=200)
        
        st.session_state.files = processed_files
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Chat interface
    st.subheader("💬 Chat")
    
    # Hiển thị lịch sử chat
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        
        if role == "user":
            st.markdown(f"""
            <div class='chat-message user-message'>
                <strong>👤 Bạn:</strong><br>
                {content if isinstance(content, str) else content[0]['text'] if content else ''}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='chat-message assistant-message'>
                <strong>🤖 AI ({selected_model}):</strong><br>
                {content}
            </div>
            """, unsafe_allow_html=True)
    
    # Chat input
    user_input = st.chat_input("Nhập tin nhắn của bạn...")
    
    if user_input and api_key:
        # Tạo message với file đính kèm
        if st.session_state.files:
            message_content = api_client.create_message_with_files(user_input, st.session_state.files)
        else:
            message_content = user_input
        
        # Thêm message của user
        user_message = {"role": "user", "content": message_content}
        st.session_state.messages.append(user_message)
        
        # Hiển thị message của user
        st.markdown(f"""
        <div class='chat-message user-message'>
            <strong>👤 Bạn:</strong><br>
            {user_input}
        </div>
        """, unsafe_allow_html=True)
        
        # Hiển thị file đính kèm nếu có
        if st.session_state.files:
            st.write("**File đính kèm:**")
            for file_info in st.session_state.files:
                st.write(f"📎 {file_info['name']} ({file_info['type']})")
        
        # Gọi API
        with st.spinner(f"🤖 {selected_model} đang suy nghĩ..."):
            response = api_client.chat_completion(
                messages=st.session_state.messages,
                model=selected_model,
                max_tokens=max_tokens,
                temperature=temperature
            )
        
        if response and "choices" in response:
            assistant_message = response["choices"][0]["message"]["content"]
            
            # Thêm response vào lịch sử
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})
            
            # Hiển thị response
            st.markdown(f"""
            <div class='chat-message assistant-message'>
                <strong>🤖 AI ({selected_model}):</strong><br>
                {assistant_message}
            </div>
            """, unsafe_allow_html=True)
            
            # Xóa file sau khi gửi
            st.session_state.files = []
        
        st.rerun()

if __name__ == "__main__":
    main()