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

package com.example.inventory.ui.item

import android.os.Build
import androidx.annotation.RequiresApi
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.inventory.data.Item
import com.example.inventory.data.ItemsRepository
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.time.LocalDateTime

/**
 * ViewModel to validate and insert items in the Room database.
 */
class ItemEntryViewModel(private val itemsRepository: ItemsRepository) : ViewModel() {

    /**
     * Holds current item ui state
     */

    
    var itemUiState by mutableStateOf(ItemUiState())
        private set

    /**
     * Updates the [itemUiState] with the value provided in the argument. This method also triggers
     * a validation for input values.
     */

    fun fetchLastItem() {
        viewModelScope.launch {
            itemsRepository.getLastItemStream().collect { item ->
                // Update itemUiState with the last item's details
                //itemUiState = item.toItemUiState(isEdit = false)
                var lastItemDetails = item.toItemDetails()
                var currentItemDetails = itemUiState.itemDetails
                var comboItemDetails = ItemDetails(
                    id = currentItemDetails.id,
                    name = currentItemDetails.name,
                    price = lastItemDetails.price,
                    quantity = lastItemDetails.quantity,
                    type = lastItemDetails.type,
                    weight = lastItemDetails.weight,
                    outside = lastItemDetails.outside
                )
                itemUiState = ItemUiState( comboItemDetails, isEntryValid = true, isEdit = false)
            }
        }
    }
    fun updateUiState(itemDetails: ItemDetails) {
        itemUiState =
            ItemUiState(itemDetails = itemDetails, isEntryValid = validateInput(itemDetails))
    }

    /**
     * Inserts an [Item] in the Room database
     */
    suspend fun saveItem() {
        if (/*validateInput()*/ true) {
            itemsRepository.insertItem(itemUiState.itemDetails.toItem())
        }
    }

    private fun validateInput(uiState: ItemDetails = itemUiState.itemDetails): Boolean {
        return with(uiState) {
            name.isNotBlank() && price.isNotBlank() && quantity.isNotBlank()
        }
    }

/*    private fun validateInput(uiState: ItemDetails = itemUiState.itemDetails): Boolean {
        return with(uiState) {
            name.isNotBlank() &&
                    when (type.toIntOrNull()) {
                        0 -> price.isNotBlank() && quantity.isNotBlank() && outside.isNotBlank() // Climbing
                        1, 2 -> weight.isNotBlank() && quantity.isNotBlank() // Hanging/Pulling
                        else -> false // Invalid type
                    }
        }
    }*/

}

/**
 * Represents Ui State for an Item.
 */
data class ItemUiState(
    val itemDetails: ItemDetails = ItemDetails(),
    val isEntryValid: Boolean = false,
    val isEdit: Boolean = false
)

data class ItemDetails(
    val id: Int = 0,
    val name: String = LocalDateTime.now().toString(),
    val price: String = "",
    val quantity: String = "",
    val type: String = "",
    val weight: String = "",
    val outside: String = ""
)

/**
 * Extension function to convert [ItemUiState] to [Item]. If the value of [ItemDetails.price] is
 * not a valid [Double], then the price will be set to 0.0. Similarly if the value of
 * [ItemUiState] is not a valid [Int], then the quantity will be set to 0
 */
@RequiresApi(Build.VERSION_CODES.O)
fun ItemDetails.toItem(): Item = Item(
    id = id,
    name = name,
    price = price.toIntOrNull() ?: 0,
    quantity = quantity.toIntOrNull() ?: 0,
    type = type.toIntOrNull() ?: 0,
    weight = weight.toDoubleOrNull() ?: 0.0,
    outside = outside.toIntOrNull() ?: 0,
)

fun Item.formatedPrice(): String {
    //return NumberFormat.getCurrencyInstance().format(price)
    return price.toString()
}

/**
 * Extension function to convert [Item] to [ItemUiState]
 */
fun Item.toItemUiState(isEntryValid: Boolean = false,isEdit: Boolean = false): ItemUiState = ItemUiState(
    itemDetails = this.toItemDetails(),
    isEntryValid = isEntryValid,
    isEdit = isEdit
)

/**
 * Extension function to convert [Item] to [ItemDetails]
 */
fun Item.toItemDetails(): ItemDetails = ItemDetails(
    id = id,
    name = name,
    price = price.toString(),
    quantity = quantity.toString(),
    type = type.toString(),
    weight = weight.toString(),
    outside = outside.toString()
)
