package com.example.inventory.ui.event

import com.example.inventory.data.Event
import java.time.LocalDateTime

data class EventUiState(
    val eventDetails: EventDetails = EventDetails(),
    val isEntryValid: Boolean = false
)

data class EventDetails(
    val id: Int = 0,
    val time: String = LocalDateTime.now().toString(),
    val type: String = "0",
    val note: String = "",
    val value: String = "0"
)

fun EventDetails.toEvent(): Event = Event(
    id = id,
    time = time,
    type = type.toIntOrNull() ?: 0,
    note = note,
    value = value.toDoubleOrNull() ?: 0.0
)

fun Event.toEventDetails(): EventDetails = EventDetails(
    id = id,
    time = time,
    type = type.toString(),
    note = note,
    value = when (type) {
        2 -> value.toInt().toString()
        else -> value.toString()
    }
)

fun Event.toEventUiState(isEntryValid: Boolean = false): EventUiState = EventUiState(
    eventDetails = toEventDetails(),
    isEntryValid = isEntryValid
)

fun eventTypeLabel(type: Int): String {
    return when (type) {
        0 -> "Injury"
        1 -> "Bodyweight"
        2 -> "RPS"
        else -> "Event"
    }
}
