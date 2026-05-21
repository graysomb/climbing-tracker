package com.example.inventory.ui.event

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.inventory.data.ItemsRepository
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class EventEditViewModel(
    savedStateHandle: SavedStateHandle,
    private val itemsRepository: ItemsRepository
) : ViewModel() {

    var eventUiState by mutableStateOf(EventUiState())
        private set

    private val eventId: Int = checkNotNull(savedStateHandle[EventEditDestination.eventIdArg])

    init {
        viewModelScope.launch {
            eventUiState = itemsRepository.getEventStream(eventId)
                .filterNotNull()
                .first()
                .toEventUiState(true)
        }
    }

    fun updateUiState(eventDetails: EventDetails) {
        eventUiState = EventUiState(eventDetails = eventDetails, isEntryValid = true)
    }

    suspend fun updateEvent() {
        itemsRepository.updateEvent(eventUiState.eventDetails.toEvent())
    }
}
