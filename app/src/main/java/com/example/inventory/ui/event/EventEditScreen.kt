package com.example.inventory.ui.event

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.inventory.InventoryTopAppBar
import com.example.inventory.R
import com.example.inventory.ui.AppViewModelProvider
import com.example.inventory.ui.navigation.NavigationDestination
import kotlinx.coroutines.launch

object EventEditDestination : NavigationDestination {
    override val route = "event_edit"
    override val titleRes = R.string.edit_event_title
    const val eventIdArg = "eventId"
    val routeWithArgs = "$route/{$eventIdArg}"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EventEditScreen(
    navigateBack: () -> Unit,
    onNavigateUp: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: EventEditViewModel = viewModel(factory = AppViewModelProvider.Factory)
) {
    val coroutineScope = rememberCoroutineScope()
    Scaffold(
        topBar = {
            InventoryTopAppBar(
                title = stringResource(EventEditDestination.titleRes),
                canNavigateBack = true,
                navigateUp = onNavigateUp
            )
        },
        modifier = modifier
    ) { innerPadding ->
        androidx.compose.foundation.layout.Column(modifier = Modifier.padding(innerPadding)) {
            EventInputForm(
                eventDetails = viewModel.eventUiState.eventDetails,
                onValueChange = viewModel::updateUiState,
                modifier = Modifier.padding(16.dp)
            )
            Button(
                onClick = {
                    coroutineScope.launch {
                        viewModel.updateEvent()
                        navigateBack()
                    }
                },
                modifier = Modifier.padding(16.dp)
            ) {
                Text(stringResource(R.string.save_action))
            }
        }
    }
}
