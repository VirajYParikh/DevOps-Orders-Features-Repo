"""
Order and Item API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from datetime import datetime
from decimal import Decimal, getcontext
from service import app
from service.models import db, init_db, Order, Item
from service.common import status  # HTTP Status Codes
from tests.factories import OrderFactory, ItemFactory

getcontext().prec = 2

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/testdb"
)
BASE_URL = "/orders"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestOrderItemServer(TestCase):
    """Order and Item Server Tests"""

    @classmethod
    def setUpClass(cls):
        """This runs once before the entire test suite"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """This runs once after the entire test suite"""
        db.session.close()

    def setUp(self):
        """This runs before each test"""
        self.client = app.test_client()
        db.session.query(Order).delete()  # clean up the last tests
        db.session.query(Item).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        """This runs after each test"""
        db.session.remove()

    def _create_orders(self, count):
        """Factory method to create pets in bulk"""
        orders = []
        for _ in range(count):
            test_order = OrderFactory()
            response = self.client.post(BASE_URL, json=test_order.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test pet",
            )
            new_order = response.get_json()
            test_order.id = new_order["id"]
            orders.append(test_order)
        return orders

    ######################################################################
    #  P L A C E   T E S T   C A S E S   H E R E
    ######################################################################

    def test_unsupported_media_type(self):
        """It should not Create when sending wrong media type"""
        order = OrderFactory()
        resp = self.client.post(
            BASE_URL, json=order.serialize(), content_type="test/html"
        )
        self.assertEqual(resp.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_index(self):
        """It should call the home page"""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should call the health page"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_get_order_list(self):
        """It should Get a list of Orders"""
        self._create_orders(5)
        resp = self.client.get(BASE_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(len(data), 5)

    def test_read_order(self):
        """It should get the order detail by sending the id"""

        order = self._create_orders(1)[0]
        resp = self.client.get(
            f"{BASE_URL}/{order.id}", content_type="application/json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(data["customer_id"], order.customer_id)
        self.assertEqual(data["status"], order.status)
        self.assertEqual(data["creation_time"], data["last_updated_time"])

    def test_get_orders_by_customer_id(self):
        """It should Get an Order by Customer Id"""
        orders = self._create_orders(3)
        resp = self.client.get(
            BASE_URL, query_string=f"customer_id={orders[1].customer_id}"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(data[0]["customer_id"], orders[1].customer_id)

    def test_get_orders_by_date(self):
        """It should Get Orders by Date"""
        orders = self._create_orders(3)
        resp = self.client.get(
            BASE_URL, query_string=f"date={orders[1].creation_time.date()}"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        date_string = data[0]["creation_time"]
        date_format = "%Y-%m-%dT%H:%M:%S.%f"
        date_obj = datetime.strptime(date_string, date_format)
        self.assertEqual(date_obj.date(), orders[1].creation_time.date())

    def test_get_orders_by_status(self):
        """It should Get Orders by Status"""
        orders = self._create_orders(3)
        resp = self.client.get(BASE_URL, query_string=f"status={orders[1].status}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(data[0]["status"], orders[1].status)

    def test_read_order_not_found(self):
        """It should not Read an Order that is not found"""
        resp = self.client.get(f"{BASE_URL}/0")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_order(self):
        """It should Create a new Order"""
        order = OrderFactory()
        resp = self.client.post(
            BASE_URL, json=order.serialize(), content_type="application/json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = resp.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_order = resp.get_json()
        print(new_order)
        self.assertEqual(
            new_order["customer_id"],
            order.customer_id,
            "Customer Id does not match",
        )
        self.assertEqual(
            Decimal(new_order["total_price"]),
            order.total_price,
            "Total price does not match",
        )
        self.assertEqual(new_order["status"], order.status, "Status does not match")
        self.assertEqual(new_order["items"], order.items, "Items don't not match")
        self.assertEqual(
            new_order["creation_time"],
            new_order["last_updated_time"],
            "Creation-time does not match last-updated_time",
        )

        # Check that the location header was correct by getting it
        resp = self.client.get(location, content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        new_order = resp.get_json()

        self.assertEqual(
            new_order["customer_id"], order.customer_id, "Customer Id does not match"
        )
        self.assertEqual(
            Decimal(new_order["total_price"]),
            order.total_price,
            "Total price does not match",
        )
        self.assertEqual(new_order["items"], order.items, "Items don't not match")
        self.assertEqual(
            new_order["creation_time"],
            new_order["last_updated_time"],
            "Creation time does not match last-updated_time",
        )

    def test_update_order(self):
        """It should Update an existing Order"""
        # create an Order to update
        test_order = OrderFactory()
        resp = self.client.post(BASE_URL, json=test_order.serialize())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # update the pet
        new_order = resp.get_json()
        self.assertEqual(new_order["creation_time"], new_order["last_updated_time"])
        new_order["customer_id"] = 100
        new_order_id = new_order["id"]
        resp = self.client.put(f"{BASE_URL}/{new_order_id}", json=new_order)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated_order = resp.get_json()
        self.assertEqual(updated_order["customer_id"], 100)
        self.assertNotEqual(
            updated_order["creation_time"], updated_order["last_updated_time"]
        )

    def test_delete_order(self):
        """It should delete the order"""

        order = self._create_orders(1)[0]
        response = self.client.delete(f"{BASE_URL}/{order.id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.data), 0)
        # make sure they are deleted
        response = self.client.get(
            f"{BASE_URL}/{order.id}", content_type="application/json"
        )
        self.assertEqual(
            response.status_code, status.HTTP_404_NOT_FOUND
        )  # 404 error after the fact

    def test_cancel_order(self):
        """It should cancel the order"""

        # create an Order to update
        test_order = OrderFactory()
        resp = self.client.post(BASE_URL, json=test_order.serialize())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # update the pet
        new_order = resp.get_json()
        new_order_id = new_order["id"]
        resp = self.client.put(f"{BASE_URL}/{new_order_id}/cancel")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated_order = resp.get_json()
        print(updated_order)
        self.assertEqual(updated_order["status"], "canceled")

    def test_bad_request(self):
        """It should not Create when sending the wrong data"""
        resp = self.client.post(BASE_URL, json={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_method_not_allowed(self):
        """It should not allow an illegal method call"""
        resp = self.client.put(BASE_URL, json={})
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    ######################################################################
    #  I T E M S   T E S T   C A S E S
    ######################################################################

    def test_add_items(self):
        """It should Add an item to an order"""
        order = self._create_orders(1)[0]
        item = ItemFactory()
        resp = self.client.post(
            f"{BASE_URL}/{order.id}/items",
            json=item.serialize(),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.get_json()
        logging.debug(data)
        self.assertEqual(data["order_id"], order.id)
        self.assertEqual(data["name"], item.name)
        self.assertEqual(Decimal(data["price"]), item.price)
        self.assertEqual(data["description"], item.description)
        self.assertEqual(data["quantity"], item.quantity)

    def test_add_item_get_order_not_found(self):
        """It should not add an item when order doesn't exist"""
        item = ItemFactory()
        resp = self.client.post(
            f"{BASE_URL}/0/items",
            json=item.serialize(),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_items_list(self):
        """It should get a list of items"""
        # add two items to order
        order = self._create_orders(1)[0]
        item_list = ItemFactory.create_batch(2)

        # Create item 1
        resp = self.client.post(
            f"{BASE_URL}/{order.id}/items", json=item_list[0].serialize()
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Create item 2
        resp = self.client.post(
            f"{BASE_URL}/{order.id}/items", json=item_list[1].serialize()
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # get the list back and make sure there are 2
        resp = self.client.get(f"{BASE_URL}/{order.id}/items")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.get_json()
        self.assertEqual(len(data), 2)

    def test_list_items_get_order_not_found(self):
        """It should not list items when order doesn't exist"""
        item = ItemFactory()
        resp = self.client.get(
            f"{BASE_URL}/0/items",
            json=item.serialize(),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_order_get_order_not_found(self):
        """It should not list items when order doesn't exist"""
        test_order = OrderFactory()
        resp = self.client.put(
            f"{BASE_URL}/0",
            json=test_order.serialize(),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_item(self):
        """It should get an item from an order"""
        # create a known item
        order = self._create_orders(1)[0]
        item = ItemFactory()
        resp = self.client.post(
            f"{BASE_URL}/{order.id}/items",
            json=item.serialize(),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        data = resp.get_json()
        logging.debug(data)
        item_id = data["id"]

        # retrieve it back
        resp = self.client.get(
            f"{BASE_URL}/{order.id}/items/{item_id}",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.get_json()
        logging.debug(data)
        self.assertEqual(data["order_id"], order.id)
        self.assertEqual(data["name"], item.name)
        self.assertEqual(Decimal(data["price"]), item.price)
        self.assertEqual(data["description"], item.description)
        self.assertEqual(data["quantity"], item.quantity)

    def test_item_not_found(self):
        """It should not get an item if it's not present"""
        order = self._create_orders(1)[0]
        resp = self.client.get(
            f"{BASE_URL}/{order.id}/items/0",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_item(self):
        """It should Update an item in an order"""
        # create a known item
        order = self._create_orders(1)[0]
        item = ItemFactory()
        resp = self.client.post(
            f"{BASE_URL}/{order.id}/items",
            json=item.serialize(),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        data = resp.get_json()
        logging.debug(data)
        item_id = data["id"]
        data["name"] = "XXXX"

        # send the update back
        resp = self.client.put(
            f"{BASE_URL}/{order.id}/items/{item_id}",
            json=data,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # retrieve it back
        resp = self.client.get(
            f"{BASE_URL}/{order.id}/items/{item_id}",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.get_json()
        logging.debug(data)
        self.assertEqual(data["id"], item_id)
        self.assertEqual(data["order_id"], order.id)
        self.assertEqual(data["name"], "XXXX")

    def test_item_not_found_when_updating(self):
        """It should not get an item if it's not present"""
        order = self._create_orders(1)[0]
        resp = self.client.put(
            f"{BASE_URL}/{order.id}/items/0",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_item(self):
        """It should Delete an Item"""
        order = self._create_orders(1)[0]
        item = ItemFactory()

        resp = self.client.post(
            f"{BASE_URL}/{order.id}/items",
            json=item.serialize(),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.get_json()
        logging.debug(data)
        item_id = data["id"]

        # send delete request
        resp = self.client.delete(
            f"{BASE_URL}/{order.id}/items/{item_id}",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        # retrieve it back and make sure item is not there
        resp = self.client.get(
            f"{BASE_URL}/{order.id}/items/{item_id}",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # Idk why, but I have to add a 'z' to put it in the end; otherwise it won't pass the CI
    def test_z_copy_order(self):
        """It should create a copy of an existing order"""

        # create an Order to update
        _order = OrderFactory()
        _order.create()
        for item in ItemFactory.create_batch(5):
            item.create()
            _order.items.append(item)
            _order.update()

        resp = self.client.post(BASE_URL, json=_order.serialize())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Copy the order
        order = resp.get_json()
        order_id = order["id"]
        resp = self.client.post(f"{BASE_URL}/{order_id}/repeat")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        new_order = resp.get_json()

        self.assertNotEqual(_order.id, new_order["id"])
        self.assertEqual(_order.customer_id, new_order["customer_id"])
        self.assertEqual(_order.status, new_order["status"])
        self.assertEqual(len(_order.items), len(new_order["items"]))

        def test_item_is_copy(item_x, item_y):
            self.assertNotEqual(item_x.id, item_y["id"])
            self.assertEqual(new_order["id"], item_y["order_id"])
            self.assertEqual(item_x.name, item_y["name"])
            self.assertEqual(item_x.price, Decimal(item_y["price"]))
            self.assertEqual(item_x.description, item_y["description"])
            self.assertEqual(item_x.quantity, item_y["quantity"])

        for i, item1 in enumerate(_order.items):
            item2 = new_order["items"][i]
            test_item_is_copy(item1, item2)

    def test_copy_order_not_found(self):
        """It should not add an item when order doesn't exist"""
        resp = self.client.post(f"{BASE_URL}/0/repeat")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_order_not_found(self):
        """It should not cancel an order when order doesn't exist"""
        resp = self.client.put(f"{BASE_URL}/0/cancel")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
