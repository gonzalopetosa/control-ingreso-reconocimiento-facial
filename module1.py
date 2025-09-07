import sqlite3
from datetime import datetime
import hashlib
import secrets
import os


def insert_usuario():
    # Ruta completa a tu base de datos
    db_path = r"C:\Users\gonza\Desktop\TP-Inicial\Data\usuarios.db"

    # Asegurarse de que el directorio existe
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Conectar a la base de datos
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()


    # Datos del usuario a insertar
    username = "gonza_operador"
    password = "password123"  # Cambia esto por una contraseña real
    email = "gonza@empresa.com"
    rostro_path = r"C:\Users\gonza\Desktop\TP-Inicial\rostros\capture.png"  # Ruta relativa o absoluta
    role = "operador"

    try:
        # Insertar el usuario
        cursor.execute('''
            INSERT INTO usuarios(username, password, email, rostro_path, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, password, email, rostro_path, role))

        conn.commit()
        user_id = cursor.lastrowid
        print(f"✅ Usuario insertado correctamente!")
        print(f"   ID: {user_id}")
        print(f"   Usuario: {username}")
        print(f"   Email: {email}")
        print(f"   Rol: {role}")

    except sqlite3.IntegrityError as e:
        print(f"❌ Error: {e}")
        print("   El usuario o email ya existen en la base de datos")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
    finally:
        conn.close()


# Ejecutar las funciones
if __name__ == "__main__":
    print("🧑 Insertando nuevo usuario...")
    insert_usuario()

    print("\n" + "="*50)
    ver_usuarios()