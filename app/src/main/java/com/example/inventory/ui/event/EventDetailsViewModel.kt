package com.example.inventory.ui.event

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.inventory.data.ItemsRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

class EventDetailsViewModel(
    savedStateHandle: SavedStateHandle,
    private val itemsRepository: ItemsRepository,
) : ViewModel() {

    private val eventId: Int = checkNotNull(savedStateHandle[EventDetailsDestination.eventIdArg])

    val uiState: StateFlow<EventDetailsUiState> =
        itemsRepository.getEventStream(eventId)
            .filterNotNull()
            .map { EventDetailsUiState(eventDetails = it.toEventDetails()) }
            .stateIn(
                scope = viewModelScope,
                started = SharingStarted.WhileSubscribed(TIMEOUT_MILLIS),
                initialValue = EventDetailsUiState()
            )

    suspend fun deleteEvent() {
        itemsRepository.deleteEvent(uiState.value.eventDetails.toEvent())
    }

    companion object {
        private const val TIMEOUT_MILLIS = 5_000L
    }
}

data class EventDetailsUiState(
    val eventDetails: EventDetails = EventDetails()
)
