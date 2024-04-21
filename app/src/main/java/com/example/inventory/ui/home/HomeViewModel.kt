/*
 * Copyright (C) 2023 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.example.inventory.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.inventory.data.Item
import com.example.inventory.data.ItemsRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.launch
import java.time.Duration
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/**
 * ViewModel to retrieve all items in the Room database.
 */
class HomeViewModel(itemsRepository: ItemsRepository) : ViewModel() {

    /**
     * Holds home ui state. The list of items are retrieved from [ItemsRepository] and mapped to
     * [HomeUiState]
     */
    private val _currentTime = MutableStateFlow("")
    val currentTime: StateFlow<String> = _currentTime.asStateFlow()

    init {
        viewModelScope.launch {
            timeTickFlow().collect {
                _currentTime.value = it
            }
        }
    }

    val homeUiState: StateFlow<HomeUiState> =
        combine(
            itemsRepository.getAllItemsStream(),
            itemsRepository.getLastItemStream()
        ) { allItems, lastItem ->
            HomeUiState(itemList = allItems, lastItem = lastItem)
        }.stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(TIMEOUT_MILLIS),
            initialValue = HomeUiState(lastItem = Item(1,LocalDateTime.now().toString(),1,1,1,1.0))
        )

    fun timeTickFlow(): Flow<String> = flow {
        while (true) {
            val currentDateTime = LocalDateTime.now()
            //val lastItem = homeUiState.value.lastItem
            //val deformatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
            //val lastTime = LocalDateTime.parse(lastItem?.name,deformatter)
            //val timeDifference = Duration.between(lastTime, currentDateTime)
            val formattedTime = currentDateTime.format(DateTimeFormatter.ofPattern("HH:mm:ss"))
            emit(formattedTime)
            delay(1000) // Update every second
        }
    }

    companion object {
        private const val TIMEOUT_MILLIS = 5_000L
    }
}

/**
 * Ui State for HomeScreen
 */
data class HomeUiState(val itemList: List<Item> = listOf(),val lastItem: Item)
