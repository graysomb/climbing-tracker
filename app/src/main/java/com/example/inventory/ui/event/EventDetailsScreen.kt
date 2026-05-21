package com.example.inventory.ui.event

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.dimensionResource
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.inventory.InventoryTopAppBar
import com.example.inventory.R
import com.example.inventory.ui.AppViewModelProvider
import com.example.inventory.ui.navigation.NavigationDestination
import kotlinx.coroutines.launch

object EventDetailsDestination : NavigationDestination {
    override val route = "event_details"
    override val titleRes = R.string.event_detail_title
    const val eventIdArg = "eventId"
    val routeWithArgs = "$route/{$eventIdArg}"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EventDetailsScreen(
    navigateToEditEvent: (Int) -> Unit,
    navigateBack: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: EventDetailsViewModel = viewModel(factory = AppViewModelProvider.Factory)
) {
    val uiState = viewModel.uiState.collectAsState()
    val coroutineScope = rememberCoroutineScope()
    Scaffold(
        topBar = {
            InventoryTopAppBar(
                title = stringResource(EventDetailsDestination.titleRes),
                canNavigateBack = true,
                navigateUp = navigateBack
            )
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = { navigateToEditEvent(uiState.value.eventDetails.id) },
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier.padding(dimensionResource(id = R.dimen.padding_large))
            ) {
                Icon(
                    imageVector = Icons.Default.Edit,
                    contentDescription = stringResource(R.string.edit_event_title),
                )
            }
        },
        modifier = modifier
    ) { innerPadding ->
        EventDetailsBody(
            eventDetails = uiState.value.eventDetails,
            onDelete = {
                coroutineScope.launch {
                    viewModel.deleteEvent()
                    navigateBack()
                }
            },
            modifier = Modifier
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
        )
    }
}

@Composable
private fun EventDetailsBody(
    eventDetails: EventDetails,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier
) {
    var deleteConfirmationRequired by rememberSaveable { mutableStateOf(false) }
    Column(
        modifier = modifier.padding(dimensionResource(id = R.dimen.padding_medium)),
        verticalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_medium))
    ) {
        EventDetailsCard(eventDetails = eventDetails, modifier = Modifier.fillMaxWidth())
        OutlinedButton(
            onClick = { deleteConfirmationRequired = true },
            shape = MaterialTheme.shapes.small,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(stringResource(R.string.delete))
        }
        if (deleteConfirmationRequired) {
            AlertDialog(
                onDismissRequest = { deleteConfirmationRequired = false },
                title = { Text(stringResource(R.string.attention)) },
                text = { Text(stringResource(R.string.delete_question)) },
                dismissButton = {
                    TextButton(onClick = { deleteConfirmationRequired = false }) {
                        Text(stringResource(R.string.no))
                    }
                },
                confirmButton = {
                    TextButton(
                        onClick = {
                            deleteConfirmationRequired = false
                            onDelete()
                        }
                    ) {
                        Text(stringResource(R.string.yes))
                    }
                }
            )
        }
    }
}

@Composable
private fun EventDetailsCard(eventDetails: EventDetails, modifier: Modifier = Modifier) {
    val type = eventDetails.type.toIntOrNull() ?: 0
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(dimensionResource(id = R.dimen.padding_medium)),
            verticalArrangement = Arrangement.spacedBy(dimensionResource(id = R.dimen.padding_medium))
        ) {
            EventRow(label = "Type", value = eventTypeLabel(type))
            EventRow(label = "Time", value = eventDetails.time)
            when (type) {
                0 -> EventRow(label = "Note", value = eventDetails.note)
                1 -> EventRow(label = "Bodyweight", value = eventDetails.value)
                2 -> EventRow(label = "RPS", value = eventDetails.value)
            }
        }
    }
}

@Composable
private fun EventRow(label: String, value: String, modifier: Modifier = Modifier) {
    Row(modifier = modifier) {
        Text(text = label, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
        Spacer(modifier = Modifier.weight(1f))
        Text(text = value)
    }
}
