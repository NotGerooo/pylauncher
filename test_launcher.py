# test_launcher.py
import pytest
from launcher import *  # Importa las funciones de tu launcher

# Test 1: Probar si una función suma correctamente
def test_suma():
    resultado = suma(2, 3)
    assert resultado == 5  # Si resultado NO es 5, el test FALLA
    print("✅ Test de suma pasó")

# Test 2: Probar si una función abre un archivo
def test_abrir_archivo():
    # Aquí simulas abrir un archivo
    resultado = abrir_archivo("archivo.txt")
    assert resultado is not None  # Verifica que NO sea None (vacío)
    print("✅ Test de abrir archivo pasó")

# Test 3: Probar si una función maneja errores
def test_division_por_cero():
    with pytest.raises(ZeroDivisionError):  # Espera un error
        division(10, 0)
    print("✅ Test de manejo de error pasó")