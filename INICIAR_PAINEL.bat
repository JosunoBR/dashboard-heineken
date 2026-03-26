@echo off
echo Instalando/Atualizando dependencias...
pip install -r requirements.txt
echo.
echo Iniciando o Painel Heineken...
python -m streamlit run 1_Auditoria_de_Pendencias.py
pause