import os
import json
import logging
import base64
import re
from typing import Dict, Any, AsyncIterator, Optional

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool

from gdrive_client import get_gdrive_client

logger = logging.getLogger(__name__)
load_dotenv()

_client = get_gdrive_client()


@tool
def upload_file(content: str, filename: str, mime_type: str = "text/plain", folder_id: str = "") -> str: # [ 1 ]
    """
    Google Drive에 파일을 업로드합니다.

    Args:
        content: 업로드할 파일 내용 (텍스트)
        filename: 저장할 파일명 (예: report.txt)
        mime_type: MIME 타입 (기본값: text/plain)
        folder_id: 저장할 폴더 ID (선택, 비워두면 기본 폴더에 저장)
    """
    try:
        from datetime import datetime
        result = _client.upload_file(
            content=content.encode('utf-8'),
            filename=filename,
            mime_type=mime_type,
            description=f"Uploaded at {datetime.now().isoformat()}",
            parent_folder_id=folder_id if folder_id else None
        )

        return json.dumps({
            "success": True,
            "message": f"파일 '{filename}' 업로드 완료",
            **result
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

@tool
def upload_base64_file(base64_content: str, filename: str, mime_type: str, folder_id: str = "") -> str:
    """
    프론트엔드에서 전달받은 Base64 인코딩된 파일 데이터를 Google Drive에 업로드합니다.
    이미지, PDF, 오디오, 엑셀 문서 등 모든 바이너리 파일 형식에 사용합니다.

    Args:
        base64_content: Base64로 인코딩된 파일 내용 (텍스트 문자열)
        filename: 저장할 파일명 (예: photo.jpg, report.pdf)
        mime_type: 파일의 MIME 타입 (예: image/jpeg, application/pdf)
        folder_id: 저장할 폴더 ID (선택, 비워두면 기본 폴더에 저장)
    """
    try:
        from datetime import datetime
        
        # 1. Base64 텍스트를 디코딩하여 원래의 바이너리 바이트(bytes) 데이터로 복원
        file_bytes = base64.b64decode(base64_content)

        # 2. 복원된 바이너리 데이터를 구글 드라이브 클라이언트에 전달
        result = _client.upload_file(
            content=file_bytes,
            filename=filename,
            mime_type=mime_type,
            description=f"Uploaded via Agent at {datetime.now().isoformat()}",
            parent_folder_id=folder_id if folder_id else None
        )

        return json.dumps({
            "success": True,
            "message": f"파일 '{filename}' 업로드 완료",
            **result
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    
@tool
def download_file_as_base64(file_id: str) -> str: # [ 2 ]
    """
    Google Drive에서 파일을 다운로드하여 Base64로 인코딩하여 반환합니다.
    RAG Agent에게 전달하여 텍스트 추출 및 인덱싱에 사용합니다.

    Args:
        file_id: 다운로드할 파일 ID 또는 storage_ref

    Returns:
        Base64 인코딩된 파일 내용과 메타데이터
    """
    try:
        result = _client.download_file_as_base64(file_id)
        if result is None:
            return json.dumps({"success": False, "error": "파일을 찾을 수 없습니다"}, ensure_ascii=False)

        return json.dumps({
            "success": True,
            **result
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def find_and_read_file_by_name(filename: str, max_chars: int = 15000) -> str:
    """
    파일명으로 Google Drive 전체를 검색한 뒤 텍스트 파일 내용을 읽습니다.
    보고서 양식 참고(test.txt 등) 요청에 **반드시** 이 도구를 사용하세요.

    Args:
        filename: 파일명 (예: test.txt)
        max_chars: 최대 읽을 문자 수 (기본 15000)
    """
    try:
        result = _client.find_and_read_by_name(filename, max_chars=max_chars)
        if result is None:
            return json.dumps({
                "success": False,
                "error": f"'{filename}' 파일을 Drive에서 찾을 수 없습니다",
            }, ensure_ascii=False)

        return json.dumps({"success": True, **result}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def read_file_content(file_id: str, max_chars: int = 15000) -> str:
    """
    Google Drive 텍스트 파일의 내용을 읽습니다. 보고서 양식·형식 참고용으로 사용합니다.

    Args:
        file_id: 파일 ID 또는 storage_ref (예: gdrive://file/abc123)
        max_chars: 최대 읽을 문자 수 (기본 5000)
    """
    try:
        result = _client.read_file_content(file_id, max_chars=max_chars)
        if result is None:
            return json.dumps({"success": False, "error": "파일을 찾을 수 없습니다"}, ensure_ascii=False)

        return json.dumps({"success": True, **result}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def get_file_info(file_id: str) -> str: # [ 1 ]
    """
    Google Drive 파일의 상세 정보를 조회합니다.

    Args:
        file_id: 조회할 파일 ID 또는 storage_ref
    """
    try:
        result = _client.get_file_info(file_id)
        if result is None:
            return json.dumps({"success": False, "error": "파일을 찾을 수 없습니다"}, ensure_ascii=False)

        return json.dumps({
            "success": True,
            "file_info": result
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def find_folder_by_name(folder_name: str) -> str: # [ 2 ]
    """
    폴더 이름으로 Google Drive에서 폴더를 검색합니다.

    Args:
        folder_name: 검색할 폴더 이름 (예: "보고서", "문서")

    Returns:
        폴더 정보 (folder_id 포함)
    """
    try:
        folders = _client.find_folder_by_name(folder_name)

        if not folders:
            return json.dumps({
                "success": False,
                "error": f"'{folder_name}' 폴더를 찾을 수 없습니다"
            }, ensure_ascii=False)

        return json.dumps({
            "success": True,
            "count": len(folders),
            "folders": folders
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def list_files(folder_name: str = "", folder_id: str = "", search_query: str = "", max_results: int = 20) -> str: # [ 1 ]
    """
    Google Drive의 파일 목록을 조회합니다.
    폴더 이름, 폴더 ID, 파일명 검색을 모두 지원합니다.

    Args:
        folder_name: 폴더 이름 (예: "보고서") - folder_id가 없을 때 폴더 검색에 사용
        folder_id: 특정 폴더 ID (직접 지정 시 우선 사용, 비워두면 기본 앱 폴더)
        search_query: 파일명 검색어 (선택, 비워두면 전체 조회)
        max_results: 최대 결과 수 (기본값: 20)

    Returns:
        파일 목록 (folder_name, folder_id, files 포함)
    """
    try:
        # folder_id가 없고 folder_name이 있으면 폴더 검색
        target_folder_id = folder_id
        found_folder_name = folder_name or "지정된 폴더"

        if not target_folder_id and folder_name:
            folders = _client.find_folder_by_name(folder_name, max_results=1)
            if not folders:
                return json.dumps({
                    "success": False,
                    "error": f"'{folder_name}' 폴더를 찾을 수 없습니다"
                }, ensure_ascii=False)
            target_folder_id = folders[0]['folder_id']
            found_folder_name = folders[0]['folder_name']
        elif not target_folder_id:
            # 기본 앱 폴더 사용
            target_folder_id = _client.app_folder_id
            found_folder_name = "기본 앱 폴더"

        # 파일 목록 조회
        query = f"name contains '{search_query}'" if search_query else None
        files = _client.list_files(query=query, page_size=max_results, folder_id=target_folder_id)

        return json.dumps({
            "success": True,
            "folder_name": found_folder_name,
            "folder_id": target_folder_id,
            "count": len(files),
            "files": files
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def delete_file(file_id: str, permanent: bool = False) -> str: # [ 2 ]
    """
    Google Drive에서 파일을 삭제합니다.

    Args:
        file_id: 삭제할 파일 ID 또는 storage_ref
        permanent: 영구 삭제 여부 (기본값: False, 휴지통으로 이동)
    """
    try:
        # 파일명 조회
        info = _client.get_file_info(file_id)
        if info is None:
            return json.dumps({"success": False, "error": "파일을 찾을 수 없습니다"}, ensure_ascii=False)

        filename = info['filename']
        success = _client.delete_file(file_id, permanent=permanent)

        if not success:
            return json.dumps({"success": False, "error": "파일 삭제 실패"}, ensure_ascii=False)

        action = "영구 삭제" if permanent else "휴지통으로 이동"
        return json.dumps({"success": True, "message": f"파일 '{filename}' {action} 완료"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def update_file(file_id: str, new_content: str = "", new_name: str = "") -> str: # [ 1 ]
    """
    Google Drive 파일을 업데이트합니다.

    Args:
        file_id: 업데이트할 파일 ID 또는 storage_ref
        new_content: 새 파일 내용 (선택)
        new_name: 새 파일명 (선택)
    """
    try:
        content_bytes = new_content.encode('utf-8') if new_content else None
        result = _client.update_file(file_id, content=content_bytes, new_name=new_name)

        return json.dumps({
            "success": True,
            "message": f"파일 '{result['filename']}' 업데이트 완료",
            **result
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def create_folder(folder_name: str, parent_folder_id: str = "") -> str: # [ 2 ]
    """
    Google Drive에 새 폴더를 생성합니다.

    Args:
        folder_name: 생성할 폴더명
        parent_folder_id: 부모 폴더 ID (선택, 비워두면 기본 앱 폴더에 생성)
    """
    try:
        result = _client.create_folder(folder_name, parent_folder_id=parent_folder_id if parent_folder_id else None)

        return json.dumps({
            "success": True,
            "message": f"폴더 '{folder_name}' 생성 완료",
            **result
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


tools = [
    upload_file,
    upload_base64_file,
    download_file_as_base64,
    find_and_read_file_by_name,
    read_file_content,
    get_file_info,
    list_files,
    find_folder_by_name,
    delete_file,
    update_file,
    create_folder
]


FILE_AGENT_SYSTEM_PROMPT = """당신은 Google Drive 파일 관리 에이전트입니다.

**양식/참고 파일 읽기 요청** (test.txt, .md 등):
1. 반드시 `find_and_read_file_by_name` 도구를 호출하세요 (파일명 그대로).
2. 파일 내용을 읽은 뒤 "파일을 읽었습니다"라고만 답하지 말고, 읽기 성공 여부를 보고하세요.
3. "내용을 직접 참조할 수 없습니다"라고 **절대** 답하지 마세요 — 도구로 읽을 수 있습니다.

**저장/업로드 요청**: upload_file 등 적절한 도구 사용.
"""

_FILENAME_PATTERN = re.compile(r"([\w\uac00-\ud7a3.-]+\.(?:txt|md|markdown))", re.IGNORECASE)
_FORMAT_READ_PATTERNS = (
    "양식 참고",
    "양식대로",
    "양식 참조",
    "참고용",
    "참고해서",
    "내용을 조회",
    "내용 조회",
    "파일을 찾아",
    "format",
    "template",
)
_SAVE_PATTERNS = (
    "저장해",
    "저장하",
    "업로드",
    "upload",
    "save",
    "저장할 파일명",
    "아래 보고서 내용",
)


def _extract_filename_from_query(query: str) -> Optional[str]:
    m = _FILENAME_PATTERN.search(query)
    return m.group(1) if m else None


def _is_format_read_request(query: str) -> bool:
    q = query.lower()
    if not _extract_filename_from_query(query):
        return False
    if any(p in q for p in _SAVE_PATTERNS):
        return False
    return any(p in q for p in _FORMAT_READ_PATTERNS)


def _direct_read_format_file(filename: str) -> Optional[dict]:
    """LLM 없이 Drive에서 양식 파일 직접 읽기"""
    try:
        _client.initialize()
        result = _client.find_and_read_by_name(filename, max_chars=15000)
        if result and result.get("content"):
            return {
                "filename": result.get("filename", filename),
                "content": result.get("content", ""),
                "mime_type": result.get("mime_type", ""),
                "truncated": result.get("truncated", False),
                "file_id": result.get("file_id", ""),
                "storage_ref": result.get("storage_ref", ""),
            }
        logger.warning(f"[FILE AGENT] Drive에서 '{filename}' 읽기 실패 (검색/다운로드)")
    except Exception as e:
        logger.warning(f"[FILE AGENT] 직접 파일 읽기 예외 ({filename}): {e}")
    return None


def _is_tool_result_message(msg) -> bool:
    msg_type = getattr(msg, "type", None)
    if msg_type == "tool":
        return True
    class_name = type(msg).__name__
    if class_name == "ToolMessage":
        return True
    name = getattr(msg, "name", None)
    if name and not getattr(msg, "tool_calls", None):
        if class_name not in ("AIMessage", "HumanMessage", "SystemMessage"):
            return True
    return False


def _extract_file_content_from_tools(tool_messages) -> Optional[dict]:
    """read_file_content 도구 결과에서 파일 원문 추출"""
    for msg in reversed(tool_messages):
        if not hasattr(msg, "content") or not msg.content:
            continue
        try:
            raw = msg.content
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict) and data.get("success") and data.get("content"):
                return {
                    "filename": data.get("filename", ""),
                    "content": data.get("content", ""),
                    "mime_type": data.get("mime_type", ""),
                    "truncated": data.get("truncated", False),
                }
        except (json.JSONDecodeError, TypeError):
            continue
    return None


class FileManagementAgent:
    """A2A 프로토콜용 에이전트 래퍼"""

    def __init__(self, model_name: str = "openai:gpt-4o"): # [ 1 ]
        self.model_name = model_name
        self.graph = None
        self.initialized = False

    async def initialize(self) -> None:
        if self.initialized:
            return
        _client.initialize()
        self.graph = create_agent(model=self.model_name, tools=tools)
        self.initialized = True
        logger.info("[FILE AGENT] [INIT] File Management Agent 초기화 완료")

    async def stream(self, query: str) -> AsyncIterator[Dict[str, Any]]:
        if not self.initialized:
            await self.initialize()

        filename = _extract_filename_from_query(query)
        if _is_format_read_request(query) and filename:
            file_content_data = _direct_read_format_file(filename)
            if file_content_data:
                logger.info(
                    f"[FILE AGENT] 양식 파일 직접 읽기 성공: {filename} "
                    f"({len(file_content_data.get('content', ''))} chars)"
                )
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": (
                        f"'{filename}' 파일을 Drive에서 읽었습니다 "
                        f"({len(file_content_data['content'])}자). "
                        "보고서 양식 참고용으로 전달합니다."
                    ),
                    "data": file_content_data,
                    "file_content": file_content_data,
                }
                return
            logger.warning(f"[FILE AGENT] 양식 파일 직접 읽기 실패, LLM fallback: {filename}")

        final_message = None
        file_list_data = None
        file_content_data = None
        tool_messages = []

        async for chunk in self.graph.astream({
            "messages": [
                ("system", FILE_AGENT_SYSTEM_PROMPT),
                ("user", query),
            ]
        }):
            for node_name, node_output in chunk.items():
                messages = node_output.get("messages", [])

                for msg in messages:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        tool_names = [tc.get('name', 'unknown') for tc in msg.tool_calls]
                        yield {
                            "is_task_complete": False,
                            "require_user_input": False,
                            "content": f"🔧 도구 실행 중... ({', '.join(tool_names)})"
                        }

                    if _is_tool_result_message(msg):
                        tool_messages.append(msg)

                    if hasattr(msg, 'content') and msg.content:
                        if not (hasattr(msg, 'tool_calls') and msg.tool_calls):
                            if not _is_tool_result_message(msg):
                                final_message = msg.content
                            try:
                                result = json.loads(msg.content)
                                if result.get("success") and "files" in result:
                                    file_list_data = result
                                    logger.info(f"[FILE AGENT] 파일 목록 발견: {len(result['files'])}개")
                            except (json.JSONDecodeError, TypeError):
                                pass

        file_content_data = _extract_file_content_from_tools(tool_messages)
        if file_content_data:
            logger.info(
                f"[FILE AGENT] 파일 원문 추출: {file_content_data.get('filename')} "
                f"({len(file_content_data.get('content', ''))} chars)"
            )

        yield {
            "is_task_complete": True,
            "require_user_input": False,
            "content": final_message if final_message else "응답을 생성하지 못했습니다.",
            "data": file_list_data or file_content_data,
            "file_content": file_content_data,
        }

"""
if __name__ == "__main__":
    import asyncio

    async def test():
        print("=" * 60)
        print("File Management Agent 테스트")
        print("=" * 60)

        agent = FileManagementAgent()
        query = input("질문을 입력하세요:")

        print(f"\n👤 Query: {query}")
        print("-" * 60)

        async for chunk in agent.stream(query):
            content = chunk.get("content", "")
            is_complete = chunk.get("is_task_complete", False)

            if not is_complete:
                print(f"{content}")
            else:
                print(f"\n💬 {content}")

    asyncio.run(test())
"""

if __name__ == "__main__":
    import asyncio
    import base64
    import mimetypes

    async def test_tool_directly():
        print("=" * 60)
        print("LLM 없이 upload_base64_file 도구 직접 기능 테스트")
        print("=" * 60)

        # 구글 드라이브 클라이언트 초기화
        _client.initialize()
        
        # 1. 테스트할 로컬 파일 경로 입력
        # (테스트용으로 크기가 1~2MB 이하인 작은 이미지나 문서를 추천합니다)
        file_path = input("테스트할 로컬 파일 경로를 입력하세요: ").strip()
        
        if not os.path.exists(file_path):
            print(f"❌ 파일이 존재하지 않습니다: {file_path}")
            return

        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        # 2. 로컬 파일 내용을 Base64 문자열로 인코딩
        print("🔄 파일을 Base64로 인코딩 중...")
        with open(file_path, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode('utf-8')

        print(f"📦 인코딩 완료 (문자열 길이: {len(encoded_string)} 자)")
        print("-" * 60)
        print("🚀 구글 드라이브 업로드 툴 직접 호출 시작...")

        # 3. 에이전트(LLM)를 거치지 않고, 데코레이터가 적용된 원래 파이썬 함수(.func) 직접 호출
        # 이렇게 하면 토큰 제한(Context Length) 문제 없이 대용량 파일도 테스트 가능합니다.
        try:
            # LangChain 툴 객체 내부의 실제 함수는 .func로 접근할 수 있습니다.
            result_json = upload_base64_file.func(
                base64_content=encoded_string,
                filename=filename,
                mime_type=mime_type,
                folder_id=""  # 특정 폴더 지정을 원하면 폴더 ID 입력
            )
            
            result = json.loads(result_json)
            if result.get("success"):
                print("\n✅ 업로드 성공!")
                print(f"💬 결과 메시지: {result.get('message')}")
                print(f"🆔 파일 ID: {result.get('file_id')}")
            else:
                print(f"\n❌ 업로드 실패: {result.get('error')}")
                
        except Exception as e:
            print(f"\n❌ 예외 발생: {str(e)}")

    asyncio.run(test_tool_directly())