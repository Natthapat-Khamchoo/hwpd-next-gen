Set-Location -Path "C:\Users\marso\OneDrive\Desktop\Natthapat-HP\เขียนโปรแกรม\hwpd next gen"
git init
git add .
git commit -m "refactor: Production overhaul with Python FastAPI Backend & React Vite Frontend"
git branch -M main
git remote remove origin 2>$null
git remote add origin https://github.com/Natthapat-Khamchoo/hwpd-next-gen.git
git push -u origin main --force
