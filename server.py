from pathlib import Path
import json
import mimetypes
from typing import List, Dict, Optional
from mcp.server.fastmcp import FastMCP, Image, Context

# MCP 서버 생성
mcp = FastMCP("Multi-Repo Access Server")

# 여러 저장소 경로 설정
REPOSITORIES = {
    "mcp-python-sdk": Path("/Users/pdstudio/Work/test-mcp/mcp-resource-repo/repos/modelcontextprotocol/python-sdk"),
    "mcp-servers": Path("/Users/pdstudio/Work/test-mcp/mcp-resource-repo/repos/modelcontextprotocol/specification"),
    "mcp-docs": Path("/Users/pdstudio/Work/test-mcp/mcp-resource-repo/repos/modelcontextprotocol/docs"),
    "mcp-specification": Path("/Users/pdstudio/Work/test-mcp/mcp-resource-repo/repos/modelcontextprotocol/specification"),
    # 더 많은 저장소 추가 가능
}

# 현재 활성화된 저장소
ACTIVE_REPO = "mcp-docs"

# 텍스트 파일로 처리할 확장자 목록
TEXT_EXTENSIONS = [
    '.py', '.md', '.mdx', '.txt', '.json', '.yml', '.yaml', 
    '.toml', '.cfg', '.ini', '.html', '.css', '.js', '.jsx', 
    '.ts', '.tsx', '.csv', '.sql', '.sh', '.bat', '.xml'
]

# 특수 처리가 필요한 파일 유형
SPECIAL_EXTENSIONS = ['.ipynb', '.png', '.jpg', '.jpeg', '.gif']

def is_text_file(file_path: Path) -> bool:
    """파일이 텍스트 파일인지 확인합니다."""
    return file_path.suffix.lower() in TEXT_EXTENSIONS

def is_special_file(file_path: Path) -> bool:
    """특수 처리가 필요한 파일인지 확인합니다."""
    return file_path.suffix.lower() in SPECIAL_EXTENSIONS

def get_active_repo_path() -> Path:
    """현재 활성화된 저장소 경로를 반환합니다."""
    return REPOSITORIES[ACTIVE_REPO]

@mcp.tool()
def switch_repository(repo_name: str) -> str:
    """
    작업할 저장소를 변경합니다.
    
    Args:
        repo_name: 변경할 저장소 이름 (사용 가능한 저장소: python-sdk, servers, ts-sdk 등)
    
    Returns:
        변경 결과 메시지
    """
    global ACTIVE_REPO
    
    if repo_name not in REPOSITORIES:
        available_repos = ", ".join(REPOSITORIES.keys())
        return f"오류: '{repo_name}'은(는) 유효한 저장소가 아닙니다. 사용 가능한 저장소: {available_repos}"
    
    ACTIVE_REPO = repo_name
    return f"저장소가 '{repo_name}'으로 변경되었습니다. 경로: {REPOSITORIES[repo_name]}"

@mcp.tool()
def list_available_repositories() -> str:
    """
    사용 가능한 모든 저장소 목록을 반환합니다.
    
    Returns:
        저장소 이름과 경로 목록
    """
    repo_info = []
    for name, path in REPOSITORIES.items():
        is_active = name == ACTIVE_REPO
        repo_info.append({
            "name": name,
            "path": str(path),
            "active": is_active,
            "exists": path.exists()
        })
    
    return json.dumps({
        "repositories": repo_info,
        "active_repository": ACTIVE_REPO
    }, ensure_ascii=False, indent=2)

@mcp.resource("repo://current")
def get_current_repo_info() -> str:
    """현재 활성화된 저장소 정보 제공"""
    repo_path = get_active_repo_path()
    
    readme_path = repo_path / "README.md"
    readme_content = ""
    if readme_path.exists() and readme_path.is_file():
        readme_content = readme_path.read_text(errors="replace")
    
    # 기본 정보 수집
    dirs = [d.name for d in repo_path.iterdir() if d.is_dir()]
    py_files = list(repo_path.glob("**/*.py"))
    
    info = {
        "name": ACTIVE_REPO,
        "path": str(repo_path),
        "directories": dirs,
        "python_files_count": len(py_files),
        "readme_available": bool(readme_content),
        "readme_excerpt": readme_content[:500] + "..." if len(readme_content) > 500 else readme_content
    }
    
    return json.dumps(info, ensure_ascii=False, indent=2)

@mcp.resource("repo://files")
def list_repo_files() -> str:
    """저장소의 파일 목록 제공"""
    repo_path = get_active_repo_path()
    files = []
    
    for f in repo_path.glob("**/*"):
        if f.is_file():
            rel_path = f.relative_to(repo_path)
            ext = f.suffix.lower()
            file_type = "text" if is_text_file(f) else "special" if is_special_file(f) else "binary"
            files.append({
                "path": str(rel_path),
                "extension": ext,
                "type": file_type,
                "size_bytes": f.stat().st_size
            })
    
    return json.dumps({
        "repository": ACTIVE_REPO,
        "path": str(repo_path),
        "total_files": len(files),
        "files": files[:100]  # 파일이 너무 많으면 100개만 표시
    }, ensure_ascii=False, indent=2)

@mcp.resource("repo://file/{file_path}")
def get_file_content(file_path: str) -> str | Image:
    """파일 내용 제공 - 다양한 파일 형식 지원"""
    repo_path = get_active_repo_path()
    
    try:
        file = repo_path / file_path
        if not file.exists():
            return f"Error: {file_path} 파일이 존재하지 않습니다."
        if not file.is_file():
            return f"Error: {file_path}는 파일이 아닙니다."
        
        file_ext = file.suffix.lower()
        
        # 1. 텍스트 파일 처리
        if is_text_file(file):
            return file.read_text(errors="replace")
        
        # 2. .ipynb 파일 처리 (JSON 형식이지만 특별 처리)
        elif file_ext == '.ipynb':
            try:
                notebook = json.loads(file.read_text(encoding='utf-8', errors='replace'))
                # 노트북에서 코드 셀과 마크다운 셀 추출
                cells_content = []
                for idx, cell in enumerate(notebook.get('cells', [])):
                    cell_type = cell.get('cell_type', '')
                    source = ''.join(cell.get('source', []))
                    
                    if cell_type == 'markdown':
                        cells_content.append(f"### 마크다운 셀 {idx+1}\n{source}\n")
                    elif cell_type == 'code':
                        code = source
                        outputs = []
                        for output in cell.get('outputs', []):
                            if 'text' in output:
                                outputs.append(''.join(output['text']))
                            elif 'data' in output and 'text/plain' in output['data']:
                                outputs.append(''.join(output['data']['text/plain']))
                        
                        output_text = '\n'.join(outputs) if outputs else "출력 없음"
                        cells_content.append(f"### 코드 셀 {idx+1}\n```python\n{code}\n```\n\n출력:\n{output_text}\n")
                
                return f"# Jupyter Notebook: {file.name}\n\n" + "\n\n".join(cells_content)
            except json.JSONDecodeError:
                return f"Error: {file_path}는 유효한 Jupyter Notebook 형식이 아닙니다."
        
        # 3. 이미지 파일 처리
        elif file_ext in ['.png', '.jpg', '.jpeg', '.gif']:
            # Image 객체 반환 - MCP가 이미지를 처리할 수 있게 함
            return Image(data=file.read_bytes(), format=file_ext[1:])
        
        # 4. 기타 바이너리 파일은 메타데이터만 반환
        else:
            mime_type = mimetypes.guess_type(file)[0] or "application/octet-stream"
            file_info = {
                "filename": file.name,
                "path": file_path,
                "repository": ACTIVE_REPO,
                "size_bytes": file.stat().st_size,
                "mime_type": mime_type,
                "message": "이 파일은 바이너리 형식이므로 내용이 표시되지 않습니다."
            }
            return json.dumps(file_info, ensure_ascii=False, indent=2)
            
    except Exception as e:
        return f"Error reading file: {str(e)}"

@mcp.tool()
def read_file(file_path: str, repo_name: Optional[str] = None) -> str:
    """
    특정 파일의 내용을 읽어옵니다.
    
    Args:
        file_path: 파일 경로 (저장소 루트 기준 상대 경로)
        repo_name: 읽을 저장소 이름 (없으면 현재 활성화된 저장소 사용)
    
    Returns:
        파일 내용 또는 오류 메시지
    """
    # 저장소 선택
    if repo_name and repo_name in REPOSITORIES:
        repo_path = REPOSITORIES[repo_name]
    else:
        repo_path = get_active_repo_path()
        repo_name = ACTIVE_REPO
    
    try:
        file = repo_path / file_path
        if not file.exists():
            return f"Error: {repo_name}/{file_path} 파일이 존재하지 않습니다."
        
        if is_text_file(file):
            return file.read_text(errors="replace")
        elif file.suffix.lower() == '.ipynb':
            # Jupyter Notebook 처리 로직
            notebook = json.loads(file.read_text(encoding='utf-8', errors='replace'))
            cells_content = []
            for idx, cell in enumerate(notebook.get('cells', [])):
                cell_type = cell.get('cell_type', '')
                source = ''.join(cell.get('source', []))
                
                if cell_type == 'markdown':
                    cells_content.append(f"### 마크다운 셀 {idx+1}\n{source}\n")
                elif cell_type == 'code':
                    cells_content.append(f"### 코드 셀 {idx+1}\n```python\n{source}\n```\n")
            
            return f"# Jupyter Notebook: {file.name}\n\n" + "\n\n".join(cells_content)
        else:
            return f"{file_path}는 텍스트 파일이 아니므로 내용을 직접 표시할 수 없습니다."
    except Exception as e:
        return f"Error reading file: {str(e)}"

@mcp.tool()
def search_across_repos(query: str, extensions: Optional[List[str]] = None) -> str:
    """
    모든 저장소에서 검색을 수행합니다.
    
    Args:
        query: 검색할 키워드
        extensions: 검색할 파일 확장자 목록 (예: [".py", ".md"])
    
    Returns:
        검색 결과 (JSON 형식)
    """
    if not extensions:
        extensions = [".py", ".md", ".txt"]
    
    all_results = {}
    
    for repo_name, repo_path in REPOSITORIES.items():
        if not repo_path.exists():
            continue
            
        repo_results = []
        
        for ext in extensions:
            if not ext.startswith('.'):
                ext = f".{ext}"
                
            for file in repo_path.glob(f"**/*{ext}"):
                if not file.is_file():
                    continue
                    
                try:
                    content = file.read_text(errors="replace")
                    if query.lower() in content.lower():
                        relative_path = file.relative_to(repo_path)
                        
                        # 검색어가 포함된 줄 찾기
                        matching_lines = []
                        for i, line in enumerate(content.splitlines()):
                            if query.lower() in line.lower():
                                matching_lines.append({
                                    "line_number": i+1,
                                    "content": line.strip()
                                })
                                
                                # 최대 5개 줄만 저장
                                if len(matching_lines) >= 5:
                                    break
                        
                        repo_results.append({
                            "file": str(relative_path),
                            "matches": content.lower().count(query.lower()),
                            "matching_lines": matching_lines
                        })
                except:
                    continue  # 읽을 수 없는 파일은 건너뜀
        
        if repo_results:
            all_results[repo_name] = repo_results
    
    return json.dumps({
        "query": query,
        "extensions": extensions,
        "total_repos_matched": len(all_results),
        "results": all_results
    }, ensure_ascii=False, indent=2)

@mcp.tool()
def find_similar_files(file_path: str, extensions: Optional[List[str]] = None) -> str:
    """
    주어진 파일과 유사한 이름 또는 확장자를 가진 다른 파일을 찾습니다.
    
    Args:
        file_path: 기준 파일 경로
        extensions: 찾을 파일 확장자 목록 (없으면 기준 파일과 동일한 확장자 사용)
    
    Returns:
        유사한 파일 목록
    """
    repo_path = get_active_repo_path()
    file = repo_path / file_path
    
    if not file.exists() or not file.is_file():
        return f"Error: {file_path}는 유효한 파일이 아닙니다."
    
    # 파일 이름과 확장자 분리
    file_stem = file.stem
    file_ext = file.suffix
    
    # 검색할 확장자 결정
    search_exts = extensions if extensions else [file_ext]
    
    similar_files = []
    
    # 1. 동일한 이름을 가진 다른 확장자 파일 찾기
    for ext in search_exts:
        if not ext.startswith('.'):
            ext = f".{ext}"
            
        for similar_file in repo_path.glob(f"**/{file_stem}{ext}"):
            if similar_file != file and similar_file.is_file():
                similar_files.append({
                    "path": str(similar_file.relative_to(repo_path)),
                    "similarity": "same_name_different_extension" if ext != file_ext else "same_name_same_extension",
                    "size_bytes": similar_file.stat().st_size
                })
    
    # 2. 유사한 이름을 가진 파일 찾기
    for similar_file in repo_path.glob(f"**/{file_stem}*"):
        if similar_file != file and similar_file.is_file() and similar_file not in similar_files:
            similar_files.append({
                "path": str(similar_file.relative_to(repo_path)),
                "similarity": "similar_name",
                "size_bytes": similar_file.stat().st_size
            })
    
    # 3. 동일한 폴더에 있는 파일 찾기
    for sibling_file in file.parent.glob("*"):
        if sibling_file != file and sibling_file.is_file():
            already_added = any(sf["path"] == str(sibling_file.relative_to(repo_path)) for sf in similar_files)
            
            if not already_added:
                similar_files.append({
                    "path": str(sibling_file.relative_to(repo_path)),
                    "similarity": "same_directory",
                    "size_bytes": sibling_file.stat().st_size
                })
    
    return json.dumps({
        "original_file": file_path,
        "repository": ACTIVE_REPO,
        "similar_files_count": len(similar_files),
        "similar_files": similar_files
    }, ensure_ascii=False, indent=2)

@mcp.tool()
def compare_files(file_path1: str, file_path2: str, repo_name1: Optional[str] = None, repo_name2: Optional[str] = None) -> str:
    """
    두 파일의 내용을 비교합니다.
    
    Args:
        file_path1: 첫 번째 파일 경로
        file_path2: 두 번째 파일 경로
        repo_name1: 첫 번째 파일의 저장소 (없으면 현재 저장소)
        repo_name2: 두 번째 파일의 저장소 (없으면 현재 저장소)
    
    Returns:
        파일 비교 결과
    """
    # 저장소 결정
    repo_path1 = REPOSITORIES[repo_name1] if repo_name1 in REPOSITORIES else get_active_repo_path()
    repo_path2 = REPOSITORIES[repo_name2] if repo_name2 in REPOSITORIES else get_active_repo_path()
    
    try:
        file1 = repo_path1 / file_path1
        file2 = repo_path2 / file_path2
        
        if not file1.exists() or not file1.is_file():
            return f"Error: {file_path1}는 유효한 파일이 아닙니다."
        if not file2.exists() or not file2.is_file():
            return f"Error: {file_path2}는 유효한 파일이 아닙니다."
            
        # 텍스트 파일인지 확인
        if not is_text_file(file1) or not is_text_file(file2):
            return "Error: 두 파일 모두 텍스트 파일이어야 합니다."
            
        # 두 파일 내용 읽기
        content1 = file1.read_text(errors="replace").splitlines()
        content2 = file2.read_text(errors="replace").splitlines()
        
        # 간단한 비교 결과
        identical = content1 == content2
        
        # 차이점 분석
        differences = []
        
        import difflib
        diff = difflib.ndiff(content1, content2)
        line_number = 0
        for line in diff:
            if line.startswith('- '):
                differences.append({
                    "type": "removed",
                    "line_number": line_number,
                    "content": line[2:]
                })
                line_number += 1
            elif line.startswith('+ '):
                differences.append({
                    "type": "added",
                    "line_number": line_number,
                    "content": line[2:]
                })
            elif line.startswith('? '):
                # 무시 (ndiff의 세부 정보 표시)
                pass
            else:
                line_number += 1
        
        # 결과 요약
        result = {
            "file1": {
                "path": file_path1,
                "repository": repo_name1 or ACTIVE_REPO,
                "line_count": len(content1),
                "size_bytes": file1.stat().st_size
            },
            "file2": {
                "path": file_path2,
                "repository": repo_name2 or ACTIVE_REPO,
                "line_count": len(content2),
                "size_bytes": file2.stat().st_size
            },
            "comparison": {
                "identical": identical,
                "differences_count": len(differences),
                "differences": differences[:20]  # 최대 20개 차이점만 표시
            }
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error comparing files: {str(e)}"

# 서버 실행
if __name__ == "__main__":
    mcp.run(transport='stdio')