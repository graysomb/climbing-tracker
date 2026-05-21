package com.example.inventory.ui.event

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

@Composable
fun EventInputForm(
    eventDetails: EventDetails,
    onValueChange: (EventDetails) -> Unit,
    modifier: Modifier = Modifier
) {
    val eventType = eventDetails.type.toIntOrNull() ?: 0

    Column(modifier = modifier) {
        OutlinedTextField(
            value = eventDetails.time,
            onValueChange = { onValueChange(eventDetails.copy(time = it)) },
            label = { Text(text = "Time") },
            colors = eventFieldColors(),
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        Row(modifier = Modifier.fillMaxWidth()) {
            Button(onClick = { onValueChange(eventDetails.copy(type = "0")) }) {
                Text(text = "Injury")
            }
            Button(onClick = { onValueChange(eventDetails.copy(type = "1")) }) {
                Text(text = "Bodyweight")
            }
            Button(onClick = { onValueChange(eventDetails.copy(type = "2")) }) {
                Text(text = "RPS")
            }
        }
        Text(
            text = eventTypeLabel(eventType),
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(vertical = 8.dp)
        )
        when (eventType) {
            0 -> {
                OutlinedTextField(
                    value = eventDetails.note,
                    onValueChange = { onValueChange(eventDetails.copy(note = it)) },
                    label = { Text(text = "Injury note") },
                    colors = eventFieldColors(),
                    modifier = Modifier.fillMaxWidth()
                )
            }
            1 -> {
                OutlinedTextField(
                    value = eventDetails.value,
                    onValueChange = { value ->
                        onValueChange(eventDetails.copy(value = value.filter { it.isDigit() || it == '.' }.take(6)))
                    },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    label = { Text(text = "Bodyweight") },
                    colors = eventFieldColors(),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
            2 -> {
                OutlinedTextField(
                    value = eventDetails.value,
                    onValueChange = { value ->
                        val digits = value.filter { it.isDigit() }.take(2)
                        val rps = digits.toIntOrNull()?.coerceIn(0, 10)?.toString() ?: ""
                        onValueChange(eventDetails.copy(value = rps))
                    },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    label = { Text(text = "RPS (0-10)") },
                    colors = eventFieldColors(),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }
        }
    }
}

@Composable
private fun eventFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
    unfocusedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
    disabledContainerColor = MaterialTheme.colorScheme.secondaryContainer,
)
