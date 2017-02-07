# Copyright 2015-2017 Allen Institute for Brain Science
# This file is part of Allen SDK.
#
# Allen SDK is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Allen SDK is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Allen SDK.  If not, see <http://www.gnu.org/licenses/>.

from allensdk.config.manifest import Manifest
import allensdk.core.json_utilities as ju
import pandas as pd
import pandas.io.json as pj
import functools
import os
from allensdk.deprecated import deprecated


class Cache(object):
    def __init__(self,
                 manifest=None,
                 cache=True):
        self.cache = cache
        self.load_manifest(manifest)

    def get_cache_path(self, file_name, manifest_key, *args):
        '''Helper method for accessing path specs from manifest keys.

        Parameters
        ----------
        file_name : string
        manifest_key : string
        args : ordered parameters

        Returns
        -------
        string or None
            path
        '''
        if self.cache:
            if file_name:
                return file_name
            elif self.manifest:
                return self.manifest.get_path(manifest_key, *args)

        return None

    def load_manifest(self, file_name):
        '''Read a keyed collection of path specifications.

        Parameters
        ----------
        file_name : string
            path to the manifest file

        Returns
        -------
        Manifest
        '''
        if file_name is not None:
            if not os.path.exists(file_name):

                # make the directory if it doesn't exist already
                dirname = os.path.dirname(file_name)
                if dirname:
                    Manifest.safe_mkdir(dirname)

                self.build_manifest(file_name)

            self.manifest = Manifest(
                ju.read(file_name)['manifest'], os.path.dirname(file_name))
        else:
            self.manifest = None

    def build_manifest(self, file_name):
        '''Creation of default path speifications.

        Parameters
        ----------
        file_name : string
            where to save it
        '''
        raise Exception(
            "This function must be defined in the appropriate subclass")

    def manifest_dataframe(self):
        '''Convenience method to view manifest as a pandas dataframe.
        '''
        return pd.DataFrame.from_dict(self.manifest.path_info,
                                      orient='index')

    @staticmethod
    def rename_columns(data,
                       new_old_name_tuples=None):
        '''Convenience method to rename columns in a pandas dataframe.

        Parameters
        ----------
        data : dataframe
            edited in place.
        new_old_name_tuples : list of string tuples (new, old)
        '''
        if new_old_name_tuples is None:
            new_old_name_tuples = []

        for new_name, old_name in new_old_name_tuples:
            data.columns = [new_name if c == old_name else c
                            for c in data.columns]

    def load_csv(self,
                 path,
                 rename=None,
                 index=None):
        '''Read a csv file as a pandas dataframe.

        Parameters
        ----------
        rename : list of string tuples (new old), optional
            columns to rename
        index : string, optional
            post-rename column to use as the row label.
        '''
        data = pd.DataFrame.from_csv(path)

        Cache.rename_columns(data, rename)

        if index is not None:
            data.set_index([index], inplace=True)

        return data

    def load_json(self,
                  path,
                  rename=None,
                  index=None):
        '''Read a json file as a pandas dataframe.

        Parameters
        ----------
        rename : list of string tuples (new old), optional
            columns to rename
        index : string, optional
            post-rename column to use as the row label.
        '''
        data = pj.read_json(path, orient='records')

        Cache.rename_columns(data, rename)

        if index is not None:
            data.set_index([index], inplace=True)

        return data

    @staticmethod
    def cacher(fn,
               *args,
               **kwargs):
        '''make an rma query, save it and return the dataframe.
    
        Parameters
        ----------
        fn : function reference
            makes the actual query using kwargs.
        path : string
            where to save the data
        query_strategy : string or None, optional
            'create' always generates the data,
            'file' loads from disk,
            'lazy' queries the server if no file exists,
            None generates the data and bypasses all caching behavior
        pre : function
            df|json->df|json, takes one data argument and returns filtered version, None for pass-through
        post : function
            df|json->?, takes one data argument and returns Object
        reader : function, optional
            path -> data, default NOP
        writer : function, optional
            path, data -> None, default NOP
        kwargs : objects
            passed through to the query function

        Returns
        -------
        Object or None
            data type depends on fn, reader and/or post methods.
        '''
        path = kwargs.pop('path', 'data.csv')
        query_strategy = kwargs.pop('query_strategy', None)
        pre = kwargs.pop('pre', lambda d: d)
        post = kwargs.pop('post', lambda d: d)
        reader = kwargs.pop('reader', None)
        writer = kwargs.pop('writer', None)

        if 'lazy' == query_strategy:
            if os.path.exists(path):
                query_strategy = 'file'
            else:
                query_strategy = 'create'

        if query_strategy is None:
            query_strategy = 'pass_through'

        if query_strategy == 'pass_through':
                data = fn(*args, **kwargs)
                # TODO: handle pre / post?
        elif query_strategy != 'file':
            if writer:
                Manifest.safe_make_parent_dirs(path)

                data = fn(*args, **kwargs)
                data = pre(data)
                writer(path, data)
            else:
                fn(*args, **kwargs)

        if reader:
            data = reader(path)
            
        if post:
            data = post(data)
            return data
        
        try:
            data
            return data
        except:
            pass

        return

    @staticmethod
    def cache_csv_json():
        return {
             'writer': lambda p, x : x.to_csv(p),
             'reader': pd.DataFrame.from_csv,
             'post': lambda x: x.to_dict('records')
        }

    @staticmethod
    def cache_csv_dataframe():
        return {
             'pre': pd.DataFrame,
             'writer': lambda p, x : x.to_csv(p),
             'reader' : pd.DataFrame.from_csv
        }

    @staticmethod
    def nocache_dataframe():
        return {
             'post': pd.DataFrame
        }

    @staticmethod
    def nocache_json():
        return {
        }

    @staticmethod
    def cache_json_dataframe():
        return {
             'writer': ju.write,
             'reader': lambda p: pj.read_json(p, orient='records')
        }

    @staticmethod
    def cache_json():
        return {
            'writer': ju.write,
            'reader' : ju.read
        }

    @staticmethod
    def cache_csv():
        return {
             'pre': pd.DataFrame,
             'writer': lambda p, x : x.to_csv(p),
             'reader': pd.DataFrame.from_csv
        }

    @deprecated
    def wrap(self, fn, path, cache,
             save_as_json=True,
             return_dataframe=False,
             index=None,
             rename=None,
             **kwargs):
        '''make an rma query, save it and return the dataframe.
    
        Parameters
        ----------
        fn : function reference
            makes the actual query using kwargs.
        path : string
            where to save the data
        cache : boolean
            True will make the query, False just loads from disk
        save_as_json : boolean, optional
            True (default) will save data as json, False as csv
        return_dataframe : boolean, optional
            True will cast the return value to a pandas dataframe, False (default) will not
        index : string, optional
            column to use as the pandas index
        rename : list of string tuples, optional
            (new, old) columns to rename
        kwargs : objects
            passed through to the query function
    
        Returns
        -------
        dict or DataFrame
            data type depends on return_dataframe option.
    
        Notes
        -----
        Column renaming happens after the file is reloaded for json
        '''
        if cache is True:
            json_data = fn(**kwargs)

            if save_as_json is True:
                ju.write(path, json_data)
            else:
                df = pd.DataFrame(json_data)
                Cache.rename_columns(df, rename)

                if index is not None:
                    df.set_index([index], inplace=True)

                df.to_csv(path)

        # read it back in
        if save_as_json is True:
            if return_dataframe is True:
                data = pj.read_json(path, orient='records')
                Cache.rename_columns(data, rename)
                if index is not None:
                    data.set_index([index], inplace=True)
            else:
                data = ju.read(path)
        elif return_dataframe is True:
            data = pd.DataFrame.from_csv(path)
        else:
            raise ValueError(
                'save_as_json=False cannot be used with return_dataframe=False')
    
        return data


def cacheable(func):
    '''decorator for rma queries, save it and return the dataframe.

    Parameters
    ----------
    fn : function reference
        makes the actual query using kwargs.
    path : string
        where to save the data
    query_strategy : string or None, optional
        'create' always gets the data from the source (server or generated),
        'file' loads from disk,
        'lazy' creates the data and saves to file if no file exists,
        None queries the server and bypasses all caching behavior
    pre : function
        df|json->df|json, takes one data argument and returns filtered version, None for pass-through
    post : function
        df|json->?, takes one data argument and returns Object
    reader : function, optional
        path -> data, default NOP
    writer : function, optional
        path, data -> None, default NOP
    kwargs : objects
        passed through to the query function

    Returns
    -------
    dict or DataFrame
        data type depends on dataframe option.

    Notes
    -----
    Column renaming happens after the file is reloaded for json
    '''
    @functools.wraps(func)
    def w(*args,
          **kwargs):
        result = Cache.cacher(func,
                              *args,
                              **kwargs)
        return result
    
    return w
