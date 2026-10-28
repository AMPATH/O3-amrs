/*
 * Copyright © 2024, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.fhir.odoo.api;

import static com.ozonehis.fhir.odoo.util.OdooValues.asDouble;
import static com.ozonehis.fhir.odoo.util.OdooValues.asInteger;

import com.odoojava.api.FilterCollection;
import com.odoojava.api.OdooApiException;
import com.odoojava.api.Row;
import com.ozonehis.fhir.odoo.OdooConstants;
import com.ozonehis.fhir.odoo.model.Product;
import com.ozonehis.fhir.odoo.model.StockQuant;
import java.util.Collection;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
@Service
public class StockQuantService extends BaseOdooService<StockQuant> implements OdooService<StockQuant> {

    @Override
    protected String modelName() {
        return OdooConstants.MODEL_STOCK_QUANT;
    }

    @Override
    protected String[] modelFields() {
        // stock.quant has no `name`; BaseOdooModel.fields() would request it and Odoo raises KeyError.
        return new String[] {"id", "product_id", "location_id", "quantity", "reserved_quantity"};
    }

    @Override
    protected StockQuant mapRowToResource(Row row) {
        StockQuant quant = new StockQuant();
        Integer id = asInteger(row.get("id"));
        if (id != null) {
            quant.setId(id);
        }
        quant.setProductId(asInteger(row.get("product_id")));
        quant.setLocationId(asInteger(row.get("location_id")));
        quant.setQuantity(asDouble(row.get("quantity")));
        quant.setReservedQuantity(asDouble(row.get("reserved_quantity")));
        return quant;
    }

    /**
     * Free quantity at a warehouse stock location (on-hand minus reserved), summed across SKUs.
     */
    public double freeQty(List<Product> products, int lotStockId) {
        if (products == null || products.isEmpty()) {
            return 0d;
        }
        double total = 0d;
        for (Product product : products) {
            try {
                FilterCollection filters = new FilterCollection();
                filters.add("product_id", "=", product.getId());
                filters.add("location_id", "child_of", lotStockId);
                Collection<StockQuant> quants = search(filters);
                for (StockQuant quant : quants) {
                    double onHand = quant.getQuantity() != null ? quant.getQuantity() : 0d;
                    double reserved = quant.getReservedQuantity() != null ? quant.getReservedQuantity() : 0d;
                    total += Math.max(0d, onHand - reserved);
                }
            } catch (OdooApiException e) {
                throw new RuntimeException(
                        "Error reading stock.quant for product " + product.getId() + " at location " + lotStockId, e);
            }
        }
        return total;
    }
}
