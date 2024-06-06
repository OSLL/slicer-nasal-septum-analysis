from ftplib import FTP
import os
import tempfile
import dicom2nifti

from typing import Callable
import importlib.util

import nibabel as nib
import numpy as np

import argparse

import pytest

RESULT_FILE_NAME = 'result.nii'
CONVERTED_FOLDER_NAME = 'converted'

def load_files_from_ftp(conn: FTP, entrypoint, tmp_folder, try_convert_to_nii, remove_dicom_after_conversion):
    def traverse_ftp(conn: FTP, p: str):
        try:
            size = conn.size(p)
        except:
            size = 0

        if size == 0:
            files = conn.nlst(p)
            for file in files:
                for t in traverse_ftp(conn, file):
                    if t == True:
                        yield p
                        return
                    else:
                        yield t

        else:
            if p.endswith('.dcm'):
                yield True
            elif p.endswith('.nii'):
                yield p

    def add_to_nii_result(folder: str):
        nii_file_list.write(os.path.join(os.path.abspath(folder), RESULT_FILE_NAME) + '\n')
        nii_file_list.flush()

    os.makedirs(os.path.join(tmp_folder, CONVERTED_FOLDER_NAME), exist_ok=True)
    with open(os.path.join(tmp_folder, CONVERTED_FOLDER_NAME, 'list.txt'), "w") as nii_file_list:
        for folder in traverse_ftp(conn, entrypoint):
            local_folder = os.path.join(tmp_folder, folder)

            if not os.path.exists(local_folder):
                print(f'loading {folder}')

                if folder.endswith('.nii'):
                    nii_folder = os.path.join(local_folder, 'nii')
                    os.makedirs(nii_folder)
                    with open(os.path.join(nii_folder, RESULT_FILE_NAME), 'wb') as f:
                        conn.retrbinary(f'RETR {folder}', f.write)
                    print()
                    print("!!!!!!!!!!FOUND NII!!!!!!!!!!")
                    print(nii_folder)
                    print()
                    add_to_nii_result(nii_folder)
                    continue

                os.makedirs(local_folder)
                for file in conn.nlst(folder):
                    if file.endswith('.dcm'):
                        name = os.path.basename(file)
                        with open(os.path.join(tmp_folder, file), 'wb') as f:
                            conn.retrbinary(f'RETR {file}', f.write)

            if try_convert_to_nii:
                nii_folder = os.path.join(local_folder, 'nii')
                os.makedirs(nii_folder, exist_ok=True)
                try:
                    print('converting to nii')
                    filename = os.path.join(nii_folder, RESULT_FILE_NAME)
                    if not os.path.exists(filename):
                        dicom2nifti.dicom_series_to_nifti(local_folder, filename)
                    if remove_dicom_after_conversion:
                        for file in os.listdir(local_folder):
                            if file.endswith('.dcm'):
                                os.remove(os.path.join(local_folder, file))
                    print()
                    print("!!!!!!!!!!DONE!!!!!!!!!!")
                    print(nii_folder)
                    print()
                    add_to_nii_result(nii_folder)
                except:
                    os.rmdir(nii_folder)
                    if remove_dicom_after_conversion:
                        for file in os.listdir(local_folder):
                            if file.endswith('.dcm'):
                                os.remove(os.path.join(local_folder, file))
                        os.removedirs(local_folder)
                    print('nope')

def get_nii_data(file_list: str):
    with open(file_list) as file:
        nii_files = [line.rstrip() for line in file]
    
    for file in nii_files:
        nii_img = nib.load(file)
        data = nii_img.get_fdata()
        yield data

def run_on_nii(file_list: str, callback: Callable[[np.ndarray], None]):
    for data in get_nii_data(file_list):
        callback(data)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='used for testing functions on files in ftp database')
    parser.add_argument("mode", choices=['load', 'nii', 'dicom'],
                        help='load - loads data from server; nii\\dicom - test function on specified data')

    parser.add_argument("--server", help='ftp server, default: \'kel.osll.ru\'', default='kel.osll.ru')
    parser.add_argument("--user", help='ftp user, default: \'storage\'', default='storage')
    parser.add_argument("--password", help='ftp password, required when load')

    parser.add_argument("--ftpdir", help='ftp file dir, default: \'medicine/computer-tomography\'',
                        default='medicine/computer-tomography')

    parser.add_argument("--convert-to-nii", help='try to convert dicom files to nii, defalut: true', default=True)
    parser.add_argument("--remove-dicom", action='store_true',
                        help='remove dicom files after conversion, default: false', default=False)

    parser.add_argument("--dir", help='path to working dir, defailt: \'./tmp\'', default='./tmp')

    parser.add_argument("--file-list", help='file with folders with nii files, required when nii or dicom')
    parser.add_argument("--file", help='file for testing, required when nii or dicom')
    parser.add_argument("--function-name", help='function for testing, required when nii or dicom')

    args = parser.parse_args()

    if args.mode == 'load':
        if args.password == None:
            exit("--password required")
        conn = FTP(args.server, args.user, args.password)
        load_files_from_ftp(conn, args.ftpdir, args.dir, args.convert_to_nii, args.remove_dicom)

    elif args.mode == 'nii':
        if args.file == None:
            exit('--file required')
        if args.file_list == None:
            exit('--file-list required')
        if args.function_name == None:
            exit('--function-name required')

        spec = importlib.util.spec_from_file_location("mod", args.file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        run_on_nii(args.file_list, getattr(mod, args.function_name))

    elif args.mode == 'dicom':
        exit("dicom mode is not supported yet")  # TODO
    else:
        exit(f"unknown option \'{args.mode}\'")

def nii_test(param_name="data", file_list="./tmp/converted/list.txt"):
    def wrapper(func):
        return pytest.mark.parametrize(param_name, get_nii_data(file_list))(func)
    return wrapper