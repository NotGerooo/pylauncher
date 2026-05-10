# test_launcher_mejorado.py
# ==========================================================
# Archivo de TESTS para tu launcher de Minecraft
# Los tests verifican que cada función funcione correctamente
# ==========================================================

import pytest
from launcher import *  # Importa todas las funciones de tu launcher


# ========== TESTS PARA FUNCIONES MATEMÁTICAS ==========

class TestMatematicas:
    """Agrupa todos los tests de matemáticas"""
    
    def test_suma_positivos(self):
        """Test: Sumar dos números positivos"""
        resultado = suma(2, 3)
        assert resultado == 5
        print("✅ Suma de positivos funciona")
    
    def test_suma_negativos(self):
        """Test: Sumar dos números negativos"""
        resultado = suma(-5, -3)
        assert resultado == -8
        print("✅ Suma de negativos funciona")
    
    def test_suma_mixtos(self):
        """Test: Sumar positivo y negativo"""
        resultado = suma(10, -3)
        assert resultado == 7
        print("✅ Suma mixta funciona")


# ========== TESTS PARA ARCHIVOS ==========

class TestArchivos:
    """Agrupa todos los tests de manejo de archivos"""
    
    def test_abrir_archivo_existente(self):
        """Test: Abrir un archivo que existe"""
        resultado = abrir_archivo("archivo.txt")
        assert resultado is not None
        print("✅ Abrir archivo existente funciona")
    
    def test_abrir_archivo_inexistente(self):
        """Test: Intentar abrir un archivo que NO existe"""
        resultado = abrir_archivo("archivo_que_no_existe.txt")
        # Debería retornar None o un error
        assert resultado is None or isinstance(resultado, Exception)
        print("✅ Manejo de archivo inexistente funciona")


# ========== TESTS PARA MANEJO DE ERRORES ==========

class TestErrores:
    """Agrupa todos los tests de manejo de errores"""
    
    def test_division_por_cero(self):
        """Test: Intentar dividir entre cero"""
        with pytest.raises(ZeroDivisionError):
            division(10, 0)
        print("✅ Error de división por cero detectado correctamente")
    
    def test_division_valida(self):
        """Test: Dividir dos números correctamente"""
        resultado = division(10, 2)
        assert resultado == 5
        print("✅ División válida funciona")
    
    def test_division_decimales(self):
        """Test: División con resultado decimal"""
        resultado = division(10, 3)
        # Comparar con tolerancia (por decimales)
        assert abs(resultado - 3.333) < 0.01
        print("✅ División con decimales funciona")


# ========== TESTS PARA MENÚ DEL LAUNCHER ==========

class TestMenu:
    """Agrupa todos los tests del menú principal"""
    
    def test_opcion_valida_1(self):
        """Test: Seleccionar opción 1"""
        resultado = ejecutar_opcion("1")
        assert resultado is not None
        print("✅ Opción 1 funciona")
    
    def test_opcion_valida_2(self):
        """Test: Seleccionar opción 2"""
        resultado = ejecutar_opcion("2")
        assert resultado is not None
        print("✅ Opción 2 funciona")
    
    def test_opcion_invalida(self):
        """Test: Seleccionar opción que NO existe"""
        resultado = ejecutar_opcion("999")
        assert resultado == "Error" or resultado is None
        print("✅ Manejo de opción inválida funciona")
    
    def test_opcion_vacia(self):
        """Test: Enviar opción vacía"""
        resultado = ejecutar_opcion("")
        assert resultado == "Error" or resultado is None
        print("✅ Manejo de opción vacía funciona")


# ========== TESTS PARAMETRIZADOS (Pruebas múltiples) ==========

@pytest.mark.parametrize("a,b,esperado", [
    (2, 3, 5),      # 2 + 3 = 5
    (0, 0, 0),      # 0 + 0 = 0
    (-1, 1, 0),     # -1 + 1 = 0
    (100, -50, 50), # 100 - 50 = 50
])
def test_suma_parametrizado(a, b, esperado):
    """
    Test: Prueba SUMA con múltiples valores
    Esto es más eficiente que escribir varios tests iguales
    """
    resultado = suma(a, b)
    assert resultado == esperado
    print(f"✅ Suma({a}, {b}) = {esperado} ✓")


# ========== TEST CON FIXTURES (Datos reutilizables) ==========

@pytest.fixture
def archivo_temporal(tmp_path):
    """
    Fixture: Crea un archivo temporal para tests
    (Esto es avanzado, pero útil)
    """
    archivo = tmp_path / "test.txt"
    archivo.write_text("contenido de test")
    return archivo


def test_leer_archivo_temporal(archivo_temporal):
    """Test: Leer el archivo temporal creado por la fixture"""
    contenido = leer_archivo(str(archivo_temporal))
    assert contenido == "contenido de test"
    print("✅ Lectura de archivo temporal funciona")


# ========== INSTRUCCIONES PARA EJECUTAR ==========

"""
CÓMO EJECUTAR ESTOS TESTS:

1. En la terminal, ve a la carpeta de tu proyecto:
   cd C:\Users\geron\Downloads\Minecraft_launcher

2. Ejecuta pytest:
   pytest test_launcher_mejorado.py

3. Para ver más detalles:
   pytest test_launcher_mejorado.py -v

4. Para ejecutar solo un test específico:
   pytest test_launcher_mejorado.py::TestMatematicas::test_suma_positivos -v

5. Para ver qué tests fallan:
   pytest test_launcher_mejorado.py -v --tb=short

SALIDA ESPERADA:
   ✅ test_suma_positivos PASSED
   ✅ test_suma_negativos PASSED
   ✅ test_division_por_cero PASSED
   ...
   ===================== 15 passed in 0.23s ======================
"""