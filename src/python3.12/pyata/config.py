#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-
# SPDX-License-Identifier: BSD-3-Clause


from typing import ClassVar, Self
from pydantic_settings import BaseSettings, SettingsConfigDict


__all__: list[str] = ['Settings']


class SettingsModel(BaseSettings):
    DEBUG: bool = False
    
    model_config = SettingsConfigDict(
        env_prefix = 'PYATA_',
        env_file   = '.env'
    )


class Settings:
    __singleton__: ClassVar[SettingsModel]

    def __new__(cls: type[Self]) -> SettingsModel:
        if not hasattr(cls, '__singleton__') or not cls.__singleton__:
            cls.__singleton__ = SettingsModel()
        return cls.__singleton__
    
    @classmethod
    def reload(cls: type[Self]) -> SettingsModel:
        cls.__singleton__ = SettingsModel()
        return cls.__singleton__
