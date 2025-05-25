#Qustellar Official Download Engine
'''
Update History 1.0.1:

1.Optimized and adapted to HTTP/2
2.Updated code structure
'''
from httpx import Client, Limits, TimeoutException, HTTPStatusError, RequestError
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time, sleep
from os import makedirs, cpu_count, remove
from os import path # Import the path module to use path.exe, path.join, path.splitext, path.getsize
from threading import Lock

# Global variables are used for progress tracking
ProcessedCount = 0
SuccessfulCount = 0
FailedCount = 0
ProgressLock = Lock()
TotalFiles = 0
ProgressTime = 0.0

def DownloadFile(client:Client,url:str,SavePath:str,FileName:str,MaxRetries:int = 3,timeout:int = 30):
    for attempt in range(MaxRetries):
        try:
            with client.stream("GET",url,timeout=timeout,follow_redirects=True) as response:
                if attempt == 0:
                    try:
                        HttpInfo = response.http_version
                        print(f"[{FileName}] Using {HttpInfo} Start {url[:70]}...")
                    except Exception:
                        pass
                response.raise_for_status()
                with open(SavePath, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                return True
        except TimeoutException:
            if attempt == MaxRetries - 1:
                print(f"\n[TIMEOUT] {FileName} ({url[:70]}) timeout (try {attempt + 1}/{MaxRetries})。")
        except HTTPStatusError as e:
            print(f"\n[HTTP Error] {FileName} ({url[:70]}) Download failed {e.response.status_code} {e.response.reason_phrase}")
            return False
        except RequestError as e:
            if attempt == MaxRetries - 1:
                print(f"\n[Network error] {FileName} ({url[:70]}) Download failed (try {attempt + 1}/{MaxRetries}): {type(e).__name__}")
        except Exception as e:
            if attempt == MaxRetries - 1:
                print(f"\n[未知错误] {FileName} ({url[:70]}) 下载时发生意外错误: {e}")
            
        if attempt < MaxRetries - 1:
            WaitTime = min(5, 2**(attempt))
            sleep(WaitTime)
        else:
            return False
    return False

def UProgress(ForcePrint:bool = False):
    """Thread safe updates and prints progress at intervals or upon completion"""
    global ProcessedCount,SuccessfulCount,FailedCount
    global ProgressTime,TotalFiles,ProgressLock

    with ProgressLock:
        CurrentTime = time()
        if ForcePrint or \
           (TotalFiles > 0 and (CurrentTime - ProgressTime > 1)) or \
           (TotalFiles > 0 and ProcessedCount == TotalFiles):
            
            if TotalFiles > 0:
                percentage = (ProcessedCount / TotalFiles) * 100
                print(f"Progress {ProcessedCount}/{TotalFiles} ({percentage:.2f}%) | "
                      f"Success  {SuccessfulCount} | Failed {FailedCount}     \r", end="")
            ProgressTime = CurrentTime
        
        if TotalFiles > 0 and ProcessedCount == TotalFiles and ForcePrint:
            print()


def MultiDownload(UrlList:list,DownloadFolder:str = "qustellar", Workers:int = 60, FileTimeout:int = 10, MaxRetries: int = 3):
    """Use httpx and multithreading to download file lists."""
    global TotalFiles,ProcessedCount,SuccessfulCount,FailedCount,ProgressTime
    TotalFiles = len(UrlList)
    if TotalFiles == 0:
        print("The URL list is empty, there are no files to download.")
        return
    ProcessedCount,SuccessfulCount,FailedCount,ProgressTime = 0,0,0,time()
    if not path.exists(DownloadFolder): # Using path.exists
        try:
            makedirs(DownloadFolder) # Using makedirs
            print(f"Create download folder: {DownloadFolder}")
        except OSError as e:
            print(f"Error: Unable to create download folder '{DownloadFolder}'. Because {e}")
            return
    
    limits_obj = Limits(max_connections=Workers + 10, max_keepalive_connections=Workers)

    with Client(http2=True, limits=limits_obj, follow_redirects=True, timeout=FileTimeout) as client:
        client.headers.update({'User-Agent':'QustellarDownloader/2.2 (httpx)'})
        
        with ThreadPoolExecutor(max_workers=Workers) as executor:
            FutureInfo = {}
            print(f"Start Download {TotalFiles} Files，Use up to {Workers} threads.")
            UProgress()
            for i, url in enumerate(UrlList):
                FileName = f"文件 {i + 1}"
                try:
                    potential_filename = url.split('/')[-1].split('?')[0]
                    if not potential_filename or len(potential_filename) > 220 or potential_filename == ".":
                        path_parts_url = [part for part in url.split('/') if part] # 避免与 os.path 冲突
                        if len(path_parts_url) > 1:
                            potential_filename = path_parts_url[-1] if len(path_parts_url[-1]) > 3 else path_parts_url[-2] + "_" + path_parts_url[-1]
                        else:
                            potential_filename = f"downloaded_file_{i+1}"
                    
                    valid_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                    cleaned_filename = ''.join(c for c in potential_filename if c in valid_chars)
                    if not cleaned_filename:
                        cleaned_filename = f"file_{i+1}"

                    if '.' not in cleaned_filename[-6:]:
                        url_path_for_ext = url.split('?')[0]
                        if '.' in url_path_for_ext[-6:]:
                            ext_candidate = url_path_for_ext.split('.')[-1]
                            if len(ext_candidate) < 5 and ext_candidate.isalnum():
                                cleaned_filename += f".{ext_candidate}"
                            else:
                                cleaned_filename += ".download"
                        else:
                            cleaned_filename += ".download"
                    filename = cleaned_filename[:200]
                except Exception:
                    filename = f"file_{i+1}.download"

                save_path = path.join(DownloadFolder, filename) # Using path.join
                
                counter = 1
                original_save_path_base, original_save_path_ext = path.splitext(save_path) # Using path.splitext
                while path.exists(save_path): # Using path.exists
                    save_path = f"{original_save_path_base}_{counter}{original_save_path_ext}"
                    counter += 1

                future = executor.submit(DownloadFile, client, url, save_path, FileName, MaxRetries, FileTimeout)
                FutureInfo[future] = (url, FileName, save_path)

            for future in as_completed(FutureInfo):
                OrigUrl, DisplayName, f_saved_path = FutureInfo[future]
                try:
                    success = future.result()
                    with ProgressLock:
                        ProcessedCount += 1
                        if success:
                            SuccessfulCount += 1
                        else:
                            FailedCount += 1
                            # Using path.exists 和 path.getsize
                            if path.exists(f_saved_path) and path.getsize(f_saved_path) == 0:
                                try:
                                    remove(f_saved_path) # Using remove
                                except OSError:
                                    pass
                except Exception as ExcMain:
                    print(f"\n[主控错误] {DisplayName} ({OrigUrl[:70]}...) 执行时产生异常: {ExcMain}")
                    with ProgressLock:
                        ProcessedCount += 1
                        FailedCount += 1
                finally:
                    UProgress()
    UProgress(ForcePrint=True)
    print(f"\n--- Review ---")
    print(f"Files {TotalFiles}")
    print(f"Successful {SuccessfulCount}")
    print(f"Failed {FailedCount}")

if __name__ == "__main__":
    Urls2Download = []
    UrlFilePath = "urls.txt"
    try:
        with open(UrlFilePath,"r",encoding="utf-8") as f:
            Urls2Download = [line.strip() for line in f if line.strip() and line.startswith("http")]
        if not Urls2Download:
            print(f"Warning: The URL file '{UrlFilePath}' is empty or does not contain a valid URL.")
    except FileNotFoundError:
        print(f"Hint: The URL file '{UrlFilePath}' was not found.")
    if not Urls2Download:
        print("Use the built-in example URL list for demonstration.")
        Urls2Download = [
            "https://lh3.googleusercontent.com/ogw/AF2bZyjUed_YKwjVk8yQyVAWGyi81ypsD8KqgLri7skSIG3L-Q=s64-c-mo"
        ] * 3
    DownloadDir = "qustellar"
    CPUCount = cpu_count()
    CurrentDownloads = min(32, CPUCount * 4 if CPUCount else 8)
    FileTimeout = 5
    RetriesPerFile = 2
    if not Urls2Download:
        print("The final URL list is empty, and the program exits.")
    else:
        print(f"Prepare to use httpx to download {len (Urls2Download)} files ..")
        print(f"Use up to {CurrentDownloads} concurrent threads.")
        print(f"The file will be saved to the folder: ./{DownloadDir}/")
        print(f"Single file timeout set to {FileTimeout} s")
        print(f"Maximum retry times per file: {RetriesPerFile}")
        print("-" * 50)
        StartTime = time()
        MultiDownload(
            Urls2Download,
            DownloadDir,
            CurrentDownloads,
            FileTimeout,
            RetriesPerFile
        )
        EndTime = time()
        print(f"\nAll download tasks have been processed. Total time: {EndTime-StartTime:.2f} seconds.")
