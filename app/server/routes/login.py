# login functions for login page
from fastapi import APIRouter, Depends, Request, HTTPException, Security, status, Header, Response
from fastapi.responses import FileResponse
from fastapi_another_jwt_auth import AuthJWT
from app.server.models.login import UserLogin, UserRegister, Settings, ResponseModel, ResponseTokenModel, \
    ErrorResponseModel
from datetime import timedelta, datetime
import os
import zipfile
from starlette.background import BackgroundTasks

from app.server.database import (
    add_token_to_blacklist,
    check_token_in_blacklist,
    add_token_to_whitelist,
    check_token_in_whitelist,
    remove_token_from_whitelist,
    get_refresh_token,
    add_user,
    validate_user_pw,
    delete_user_db,
    return_user_role,
    change_db_user_modify_online,
    check_sensorName_exists,
    check_sensorID_exists,
    retrieve_sensor_list,
)

router = APIRouter()

settings = Settings()

work_dir = os.getcwd()  # directory from which the script is executed, "sensor-management-system" is assumed


@AuthJWT.load_config
def get_config():
    return settings


def remove_file(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


@router.get('/auth', response_description="Successfully authenticated")
async def auth(Authorize: AuthJWT = Depends()):
    if not await validate_access_token_rights(Authorize=Authorize, required_permissions=["admin", "user", "sensor"]):
        return ErrorResponseModel(401, "Unauthorized.")
    return ResponseModel("", "Authentication Successful")


@router.post('/userlogin', response_description="Successfully logged in")
async def userlogin(credentials: UserLogin, Authorize: AuthJWT = Depends()):
    # credentials in body (is not logged by nginX)
    username = credentials.username
    password = credentials.password

    bytes = password.encode('utf-8')

    # check if user in database
    valid_user = await validate_user_pw(username, bytes)
    if not valid_user:
        return ErrorResponseModel(403, "Invalid Login.")

    # revoke old maybe available tokens of the user. Avoids having multiple valid tokens.
    await revoke_tokens_by_sub(username)

    # get user role from database & create tokens
    role = await return_user_role(username)
    user_role = {'role': [role]}
    expires_access_token = timedelta(seconds=settings.user_access_token_validity)
    expires_refresh_token = timedelta(seconds=settings.user_refresh_token_validity)
    access_token = Authorize.create_access_token(subject=username,
                                                 algorithm="HS256",
                                                 expires_time=expires_access_token,
                                                 user_claims=user_role)
    jti_acc = Authorize.get_raw_jwt(access_token)["jti"]
    exp_acc = Authorize.get_raw_jwt(access_token)["exp"]
    refresh_token = Authorize.create_refresh_token(subject=username,
                                                   algorithm="HS256",
                                                   expires_time=expires_refresh_token)
    jti_ref = Authorize.get_raw_jwt(refresh_token)["jti"]
    exp_ref = Authorize.get_raw_jwt(refresh_token)["exp"]
    print(f"userlogin.acc-token: jti={jti_acc}, exp={exp_acc}")
    print(f"userlogin.ref-token: jti={jti_ref}, exp={exp_ref}")

    success = await add_token_to_whitelist(jti_ref, username, exp_ref, jti_acc, exp_acc)
    if not success:
        return ErrorResponseModel(500, "Unable to create JWT.")

    # set user online
    await change_db_user_modify_online(username)

    # Set the JWT cookies in the response
    Authorize.set_access_cookies(access_token)
    Authorize.set_refresh_cookies(refresh_token)
    return ResponseModel("", "Login Successful")


# register new user
@router.post('/register')
async def register(user: UserRegister, _Authorize: AuthJWT = Depends()):
    # requires permissions:admin
    if not await validate_access_token_rights(Authorize=_Authorize, required_permissions=["admin"]):
        return ErrorResponseModel(401, "Unauthorized.")

    # currently registered "test users:"
    # 1. username: alice                 2. username: bob                3. username: dummy
    #   password: alice123                 password: bob123                password: dummy123
    #   email: alice@email.com             email: bob@email.com            email: dummy@email.com
    #   role: user                         role: admin                     role: sensor

    added_user, error_msg = await add_user(user.email, user.username, user.password, user.role)
    if not added_user:
        return ErrorResponseModel(500, "Error: " + error_msg)
    return ResponseModel("", "Registration Successful")


@router.post('/refresh')
async def refresh(Authorize: AuthJWT = Depends()):
    # requires a valid refresh token. returns a new refresh- and acces-token
    if not await __validate_refresh_token(Authorize=Authorize):
        return ErrorResponseModel(401, "Invalid Token.")

    # get user role from database & create tokens
    current_user = Authorize.get_jwt_subject()
    sensor_exists = await check_sensorName_exists(sensorName=current_user)
    if sensor_exists:
        role = 'sensor'
        expires_access_token = timedelta(seconds=settings.sensor_access_token_validity)
        expires_refresh_token = timedelta(seconds=settings.sensor_refresh_token_validity)
    else:
        await change_db_user_modify_online(current_user)   # set user online
        role = await return_user_role(current_user)
        expires_access_token = timedelta(seconds=settings.user_access_token_validity)
        expires_refresh_token = timedelta(seconds=settings.user_refresh_token_validity)
    user_role = {'role': [role]}

    access_token_new = Authorize.create_access_token(subject=current_user,
                                                     algorithm="HS256",
                                                     expires_time=expires_access_token,
                                                     user_claims=user_role)
    jti_acc = Authorize.get_raw_jwt(access_token_new)["jti"]
    exp_acc = Authorize.get_raw_jwt(access_token_new)["exp"]
    refresh_token_new = Authorize.create_refresh_token(subject=current_user,
                                                       algorithm="HS256",
                                                       expires_time=expires_refresh_token)
    jti_ref = Authorize.get_raw_jwt(refresh_token_new)["jti"]
    exp_ref = Authorize.get_raw_jwt(refresh_token_new)["exp"]
    sub_ref = Authorize.get_raw_jwt(refresh_token_new)["sub"]
    print(f"refresh.new-acc-token: jti={jti_acc}, exp={exp_acc}")
    print(f"refresh.new-ref-token: jti={jti_ref}, exp={exp_ref}")

    # first revoke the old tokens, then add the new tokens
    await __revoke_tokens(Authorize)
    success = await add_token_to_whitelist(jti_ref, sub_ref, exp_ref, jti_acc, exp_acc)
    if not success:
        return ErrorResponseModel(500, "Unable to create new refreshToken.")

    # Set the JWT cookies in the response
    Authorize.set_access_cookies(access_token_new)
    Authorize.set_refresh_cookies(refresh_token_new)

    if role == "sensor":
        return ResponseTokenModel(access_token_new, refresh_token_new)
    else:
        return ResponseModel("", "Tokens successfully refreshed.")


@router.get('/sensor_token/{_sensor_id}')
async def create_sensor_tokens(_sensor_id: str, background_tasks: BackgroundTasks, _Authorize: AuthJWT = Depends()):
    # requires permissions:admin
    if not await validate_access_token_rights(Authorize=_Authorize, required_permissions=["admin"]):
        return ErrorResponseModel(401, "Unauthorized.")

    # check sensorName
    sensor_exists = await check_sensorID_exists(_sensor_id)
    if not sensor_exists:
        return ErrorResponseModel(409, "Sensor not existing.")

    # remove possible old refresh-tokens. Avoids having multiple valid tokens.
    sensor_obj = await retrieve_sensor_list(_sensor_id)
    sensor_name = sensor_obj["sensor_name"]
    await revoke_tokens_by_sub(sensor_name)

    # prepare tokens
    user_role = {'role': ["sensor"]}
    expires_access_token = timedelta(seconds=settings.sensor_access_token_validity)
    expires_refresh_token = timedelta(seconds=settings.sensor_refresh_token_validity)
    access_token = _Authorize.create_access_token(subject=sensor_name,
                                                  algorithm="HS256",
                                                  expires_time=expires_access_token,
                                                  user_claims=user_role)
    jti_acc = _Authorize.get_raw_jwt(access_token)["jti"]
    exp_acc = _Authorize.get_raw_jwt(access_token)["exp"]
    refresh_token = _Authorize.create_refresh_token(subject=sensor_name,
                                                    algorithm="HS256",
                                                    expires_time=expires_refresh_token)
    jti_ref = _Authorize.get_raw_jwt(refresh_token)["jti"]
    exp_ref = _Authorize.get_raw_jwt(refresh_token)["exp"]
    sub_ref = _Authorize.get_raw_jwt(refresh_token)["sub"]
    success = await add_token_to_whitelist(jti_ref, sub_ref, exp_ref, jti_acc, exp_acc)
    if not success:
        return ErrorResponseModel(500, "Unable to create refreshToken.")

    # write tokens in files
    base_path = work_dir + '/app/server/file_uploads/'
    accToken_filename = sensor_name + "_accesstoken.txt"
    accToken_filepath = base_path + accToken_filename
    with open(accToken_filepath, "w+") as accToken_file:
        accToken_file.write(access_token)
    refToken_filename = sensor_name + "_refreshtoken.txt"
    refToken_filepath = base_path + refToken_filename
    with open(refToken_filepath, "w+") as refToken_file:
        refToken_file.write(refresh_token)
    # zip it
    zip_name = sensor_name + "_tokens.zip"
    zip_filepath = base_path + zip_name
    zf = zipfile.ZipFile(zip_filepath, "w")
    zf.write(accToken_filepath, accToken_filename)
    zf.write(refToken_filepath, refToken_filename)
    zf.close()
    # cleanup
    if os.path.exists(accToken_filepath):
        os.remove(accToken_filepath)
    if os.path.exists(refToken_filepath):
        os.remove(refToken_filepath)
    background_tasks.add_task(remove_file, zip_filepath)

    # prepare the response
    if os.path.isfile(zip_filepath):
        return FileResponse(zip_filepath, filename=zip_name)
    return ErrorResponseModel(500, "Token file can not be written.")


@router.delete('/logout')
async def logout(Authorize: AuthJWT = Depends()):
    # permissions: user, admin, sensor
    if not await validate_access_token_rights(Authorize=Authorize, required_permissions=["user", "admin", "sensor"]):
        raise ErrorResponseModel(401, "Unauthorized.")

    await __revoke_tokens(Authorize)
    return ResponseModel("", "Successful logout")


@router.delete('/delete_user')
async def delete_user(user: UserRegister, Authorize: AuthJWT = Depends()):
    # permissions: admin
    if not await validate_access_token_rights(Authorize=Authorize, required_permissions=["admin"]):
        return ErrorResponseModel(401, "Unauthorized.")

    user_deleted = await delete_user_db(user.email, user.username)
    if not user_deleted:
        return ErrorResponseModel(500, "Could not delete user.")
    # if the current user is deleted, log out
    if user.username == Authorize.get_raw_jwt()["sub"]:
        await logout(Authorize=Authorize)
    # else remove the users token from whitelist and add user to blacklist
    else:
        await revoke_tokens_by_sub(user.username)

    return ResponseModel("", "User successfully deleted.")


# ---------------------------------------------------
# ----------- server internal methods ---------------
# ---------------------------------------------------

# async def validate_access_token_rights(Authorize: AuthJWT = Depends(), required_permissions: [str] = [""]):
async def validate_access_token_rights(Authorize: AuthJWT, required_permissions=None):
    # Checks if jwt_access_token is valid (incl. not expired and not blacklisted)
    #        and if the token has the correct rights to continue
    if required_permissions is None:
        required_permissions = [""]
    if await __validate_access_token(Authorize=Authorize):
        if await __check_token_rights(Authorize=Authorize, required_permissions=required_permissions):
            return True
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient rights.")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token!.")


# @router.post('/validate_access_token')
async def __validate_access_token(Authorize: AuthJWT):
    # returns true if access token valid (incl. not expired) and not blacklisted
    #        false otherwise

    try:
        Authorize.jwt_required()
        jti = Authorize.get_raw_jwt()['jti']
        if await check_token_in_blacklist(jti):
            return False
    except Exception as ex:
        # print(f"__validate_access_token: type(exception): ", type(ex))
        return False
    return True


# @router.post('/valid_refresh_token')
async def __validate_refresh_token(Authorize: AuthJWT):
    # returns true if refresh token valid and not blacklisted
    #        false otherwise 
    try:
        Authorize.jwt_refresh_token_required()
        jti = Authorize.get_raw_jwt()['jti']
        if await check_token_in_whitelist(jti):
            return True
    except Exception as ex:
        # print(f"__validate_refresh_token: type(exception): ", type(ex))
        return False
    return False


async def __check_token_rights(Authorize: AuthJWT, required_permissions=None):
    if required_permissions is None:
        required_permissions = [""]
    try:
        role = Authorize.get_raw_jwt()['role']
        if type(role) == list:
            role = role[0]
        if not (role in required_permissions):
            return False
    except Exception:
        return False
    return True


async def __revoke_tokens(_Authorize: AuthJWT):
    sub = _Authorize.get_raw_jwt()['sub']
    revoke_success = await revoke_tokens_by_sub(
        sub)  # only returns False if no refresh-token is available, which can't be.
    if revoke_success:
        # _Authorize.unset_jwt_cookies()  # works better without (it creates empty access- & refresh-cookies)
        return True
    return ErrorResponseModel(500, "Error during token revokation.")


async def revoke_tokens_by_sub(sub: str):
    refresh_token = await get_refresh_token(sub)
    if not refresh_token:
        # if no refresh-token with the given sub is available return
        return False
    # if not yet expired, add access-token to the blacklist
    acc_jti = refresh_token["sibling_jti"]
    acc_exp = refresh_token["sibling_exp"]
    now_stamp = datetime.utcnow().timestamp()
    if acc_exp >= now_stamp:
        access_token_revoked = await add_token_to_blacklist(acc_jti, sub, acc_exp)
        if not access_token_revoked:
            return ErrorResponseModel(500, "Old accessToken not logged out clean.")
    # then remove the refresh-token from the whitelist
    ref_jti = refresh_token["jti"]
    refresh_token_revoked = await remove_token_from_whitelist(ref_jti)
    if not refresh_token_revoked:
        return ErrorResponseModel(500, "Old refreshToken not logged out clean.")
    return True


async def verify_tokens_is_admin_or_target_sub(_Authorize: AuthJWT, target_sub: str) -> bool:
    is_admin = await __check_token_rights(_Authorize, ["admin"])
    if is_admin:
        return True
    sub = _Authorize.get_raw_jwt()['sub']
    if sub == target_sub:
        return True
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient rights.")
