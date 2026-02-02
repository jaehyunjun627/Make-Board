<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>selectProduct.jsp</title>
<link rel="stylesheet" type="text/css" href="../css/fromcss.css" />
</head>
<body>

	<%
	request.setCharacterEncoding("utf-8");
	String username = request.getParameter("username");
	if (username == null) {
		username = (String) session.getAttribute("username");

	}
	session.setAttribute("username", username);
	%>

	<div align="center">
		<h2>상품 선택</h2>

		<p>
			<strong><%=session.getAttribute("username")%></strong>님 환영합니다


		</p>

		<form action="addProduct.jsp" method="get">
			<label> 상품을 고르세요</label> <select name="product">
				<option value="사과">사과</option>
				<option value="귤">귤</option>
				<option value="파인애플">파인애플</option>
				<option value="복숭아">복숭아</option>
				<option value="자몽">자몽</option>
			</select>
			<p />
			<input type="submit" value="추가" />
		</form>
		<hr />
		<a href="viewCart.jsp">장바구니 확인</a>
		
	</div>
</body>
</html>