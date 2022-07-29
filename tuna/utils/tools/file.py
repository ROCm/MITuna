import os
import dill

from tuna.utils.helpers import SIZE_UNITS


def get_extension(filepath):
	return os.path.splitext(filepath)[1]


def get_files(directory, extension=None, full_file_path=True):
	files = []
	for item in os.listdir(directory):
		item_path = os.path.join(directory, item)
		if os.path.isfile(item_path):
			if full_file_path:
				files.append(item_path)
			else:
				files.append(item)

	if extension is None:
		return files
	else:
		return [file for file in files if get_extension(file) == extension]


def get_txt_files(directory, full_file_path=True):
    return get_files(directory,
                     extension='.txt',
                     full_file_path=full_file_path)


def save(data, path, mode='w'):
    with open(path, mode) as file:
        file.write(data)

def write(data, path):
    save(data, path, mode='w')

def append(data, path):
    save(data, path, mode='a')


def dump_obj(obj, path):
    with open(path, 'wb') as file:
        dill.dump(obj, file)


def load_obj(path):
    with open(path, 'rb') as file:
        obj = dill.load(file)
        return obj

def get_size(path, units: SIZE_UNITS = SIZE_UNITS.BYTE):
    size_in_bytes = os.path.getsize(path)
    return size_in_bytes / units.value
