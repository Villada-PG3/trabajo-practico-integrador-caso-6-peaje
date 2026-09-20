COMO CORRER EL PROGRAMA:

# 1. Clonar el repositorio y entrar a la carpeta
git clone <URL-del-repositorio>
cd trabajo-practico-integrador-caso-6-peaje

# 2. Crear y activar el entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar las dependencias
pip install -r requirements.txt

# Crear las tablas
python manage.py migrate

# Cargar categorías de vehículos y tarifas
python manage.py loaddata categorias_vehiculos

# 4. Crear el SUPERUSUARIO
python manage.py createsuperuser

# 5.

python manage.py runserver