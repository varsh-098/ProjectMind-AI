@echo off
echo ========================================================
echo  Starting Local Nemotron LLM Server (Port 8082)
echo ========================================================
llama-server.exe -m "%USERPROFILE%\.cache\huggingface\hub\models--nvidia--NVIDIA-Nemotron-3-Nano-4B-GGUF\blobs\be5d9a656a51922f24f1f09a759cebb694e1f5d9728bf0ef9f8c972c5a0b5ef2" --port 8082 --host 127.0.0.1 -ngl 0 --ctx-size 4096
pause

