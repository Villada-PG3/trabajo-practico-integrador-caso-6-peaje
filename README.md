COMO CORRER EL PROGRAMA:

# 1. Clonar el repositorio y entrar a la carpeta
git clone <URL-del-repositorio>
cd trabajo-practico-integrador-caso-6-peaje

# 2. Crear y activar el entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar las dependencias
pip install -r requirements.txt

# 4. Crear las tablas
python manage.py migrate

# 5. Cargar categorías, tarifas, rutas, estaciones y casillas
python manage.py loaddata categorias_vehiculos

# 6. Crear el SUPERUSUARIO
python manage.py createsuperuser

# 7. Iniciar servidor web

python manage.py runserver