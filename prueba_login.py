from dotenv import load_dotenv
load_dotenv()


from utils_interna import login

result = login("lcibils", "Emmajkj$3459")

if result.success:
    user = result.user
    print(f"Bienvenido, {user.display_name}")
    print(f"Email:        {user.email}")
    print(f"Departamento: {user.department}")
    print(f"Cargo:        {user.title}")
    print(f"Grupos:       {user.groups}")
else:
    print(f"Error: {result.error}")
